// Resolve Java concept-rename authority and impacts with only the host JDK.
//
// Java source-file mode keeps the copied closure to this file. Public top-level
// TypeElement identity is the only rename authority; strings, annotations,
// reflection, generated sources, and framework behavior remain lexical defers.
import com.sun.source.tree.AnnotationTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.IdentifierTree;
import com.sun.source.tree.ImportTree;
import com.sun.source.tree.LiteralTree;
import com.sun.source.tree.MemberSelectTree;
import com.sun.source.tree.MethodInvocationTree;
import com.sun.source.tree.Tree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.TreePath;
import com.sun.source.util.TreePathScanner;
import com.sun.source.util.Trees;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import javax.lang.model.element.Element;
import javax.lang.model.element.Modifier;
import javax.lang.model.element.PackageElement;
import javax.lang.model.element.TypeElement;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

class JavaIdentifierEvidence {
    private record Options(
        Path root,
        Path output,
        List<String> oldTerms,
        List<String> newTerms,
        List<Path> sources
    ) {}

    private record Declaration(
        String name,
        String qualifiedName,
        String file,
        int line,
        String side
    ) {}

    private record Occurrence(
        String name,
        String file,
        int line,
        long start,
        String classification,
        String syntax
    ) {}

    private record DeferredReference(
        String kind,
        String file,
        int line,
        String text,
        String reason
    ) {}

    public static void main(String[] args) {
        Options options;
        try {
            options = parseArgs(args);
        } catch (IllegalArgumentException error) {
            System.err.println(error.getMessage());
            System.exit(2);
            return;
        }

        int exit = 0;
        try {
            run(options);
        } catch (Outcome outcome) {
            exit = outcome.exit;
            try {
                writeAtomic(options.output, json(outcome.payload) + "\n");
            } catch (Exception writeError) {
                System.err.println(writeError.getMessage());
                System.exit(2);
                return;
            }
        } catch (Exception error) {
            exit = 2;
            try {
                writeAtomic(options.output, json(mapOf(
                    "status", "failed",
                    "reason", message(error),
                    "authority_status", "unavailable",
                    "declarations", mapOf("old", List.of(), "new", List.of()),
                    "occurrences", List.of(),
                    "deferred_references", List.of(),
                    "resolution_diagnostics", List.of(message(error))
                )) + "\n");
            } catch (Exception ignored) {
                // The original failure is the useful diagnostic.
            }
        }
        if (exit != 0) System.exit(exit);
    }

    private static Options parseArgs(String[] args) {
        Path root = null;
        Path output = null;
        List<String> oldTerms = new ArrayList<>();
        List<String> newTerms = new ArrayList<>();
        List<String> sourceValues = new ArrayList<>();
        for (int index = 0; index < args.length; index++) {
            String flag = args[index];
            if (index + 1 >= args.length) throw usage();
            String value = args[++index];
            switch (flag) {
                case "--project-root" -> {
                    if (root != null) throw usage();
                    root = Path.of(value).toAbsolutePath().normalize();
                }
                case "--output" -> {
                    if (output != null) throw usage();
                    output = Path.of(value).toAbsolutePath().normalize();
                }
                case "--old-term" -> oldTerms.add(value);
                case "--new-term" -> newTerms.add(value);
                case "--source" -> sourceValues.add(value);
                default -> throw usage();
            }
        }
        if (root == null || output == null || oldTerms.isEmpty() || newTerms.isEmpty()
            || sourceValues.isEmpty()) throw usage();
        if (!Files.isDirectory(root, LinkOption.NOFOLLOW_LINKS) || Files.isSymbolicLink(root)) {
            throw new IllegalArgumentException("project root must be a non-symlink directory");
        }
        Path selectedRoot = root;
        List<Path> sources = new ArrayList<>();
        for (String value : sourceValues) {
            Path source = Path.of(value);
            if (!source.isAbsolute()) source = root.resolve(source);
            source = source.toAbsolutePath().normalize();
            if (!source.startsWith(root) || !Files.isRegularFile(source, LinkOption.NOFOLLOW_LINKS)
                || Files.isSymbolicLink(source) || traversesSymlink(root, source)) {
                throw new IllegalArgumentException("Java source must be a contained regular file: " + value);
            }
            sources.add(source);
        }
        sources.sort(Comparator.comparing(path -> relative(selectedRoot, path)));
        return new Options(selectedRoot, output, List.copyOf(oldTerms), List.copyOf(newTerms), sources);
    }

    private static IllegalArgumentException usage() {
        return new IllegalArgumentException(
            "usage: java_identifier_evidence.java --project-root ROOT --output FILE "
                + "--old-term TERM --new-term TERM --source FILE [--source FILE ...]"
        );
    }

    private static void run(Options options) throws Exception {
        if (Runtime.version().feature() < 17) {
            throw unsupported("JDK 17 or newer is required; found " + Runtime.version());
        }
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) throw unsupported("A full JDK with javac is required.");

        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        List<CompilationUnitTree> units = new ArrayList<>();
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(
            diagnostics, Locale.ROOT, StandardCharsets.UTF_8
        )) {
            JavacTask task = (JavacTask) compiler.getTask(
                null,
                manager,
                diagnostics,
                List.of("--release", "17", "-proc:none"),
                null,
                manager.getJavaFileObjectsFromPaths(options.sources)
            );
            task.parse().forEach(units::add);
            if (hasErrors(diagnostics)) throw failed(diagnosticPayload(options, diagnostics, "syntax_error"));
            task.analyze();
            if (hasErrors(diagnostics)) {
                throw failed(diagnosticPayload(options, diagnostics, "unresolved_compilation"));
            }
            Trees trees = Trees.instance(task);
            Map<URI, Path> paths = new HashMap<>();
            for (Path source : options.sources) paths.put(source.toUri(), source);

            Set<String> oldKeys = normalized(options.oldTerms);
            Set<String> newKeys = normalized(options.newTerms);
            List<Declaration> declarations = declarations(
                options.root, units, paths, trees, oldKeys, newKeys
            );
            List<Declaration> oldDeclarations = declarations.stream()
                .filter(item -> item.side.equals("old")).toList();
            List<Declaration> newDeclarations = declarations.stream()
                .filter(item -> item.side.equals("new")).toList();
            String authorityStatus = authorityStatus(oldDeclarations, newDeclarations);
            Map<String, String> authorities = new HashMap<>();
            if (oldDeclarations.size() == 1) {
                authorities.put(oldDeclarations.get(0).qualifiedName, "old_concept_symbol");
            }
            if (newDeclarations.size() == 1) {
                authorities.put(newDeclarations.get(0).qualifiedName, "new_concept_symbol");
            }

            List<Occurrence> occurrences = new ArrayList<>();
            List<DeferredReference> deferred = new ArrayList<>();
            for (CompilationUnitTree unit : units) {
                Path file = paths.get(unit.getSourceFile().toUri());
                scanUnit(
                    options.root,
                    unit,
                    file,
                    trees,
                    oldKeys,
                    newKeys,
                    authorities,
                    occurrences,
                    deferred
                );
            }
            occurrences = deduplicateOccurrences(occurrences);
            deferred = deduplicateDeferred(deferred);
            Map<String, Object> payload = mapOf(
                "status", "resolved",
                "analyzer", "jdk-compiler-tree-type-api",
                "java_version", Runtime.version().toString(),
                "minimum_jdk", 17,
                "compiler_mode", "JavacTask.parse+analyze --release 17 -proc:none",
                "authority_rule", "public top-level TypeElement identity",
                "authority_status", authorityStatus,
                "files", options.sources.stream().map(path -> relative(options.root, path)).toList(),
                "declarations", mapOf(
                    "old", oldDeclarations.stream().map(JavaIdentifierEvidence::declarationMap).toList(),
                    "new", newDeclarations.stream().map(JavaIdentifierEvidence::declarationMap).toList()
                ),
                "occurrences", occurrences.stream().map(JavaIdentifierEvidence::occurrenceMap).toList(),
                "deferred_references", deferred.stream().map(JavaIdentifierEvidence::deferredMap).toList(),
                "resolution_diagnostics", List.of()
            );
            writeAtomic(options.output, json(payload) + "\n");
        }
    }

    private static List<Declaration> declarations(
        Path root,
        List<CompilationUnitTree> units,
        Map<URI, Path> paths,
        Trees trees,
        Set<String> oldKeys,
        Set<String> newKeys
    ) {
        List<Declaration> declarations = new ArrayList<>();
        for (CompilationUnitTree unit : units) {
            Path file = paths.get(unit.getSourceFile().toUri());
            for (Tree declaration : unit.getTypeDecls()) {
                TreePath path = TreePath.getPath(unit, declaration);
                Element element = path == null ? null : trees.getElement(path);
                if (!(element instanceof TypeElement type)
                    || !(type.getEnclosingElement() instanceof PackageElement)
                    || !type.getModifiers().contains(Modifier.PUBLIC)) continue;
                String key = normalize(type.getSimpleName().toString());
                String side = oldKeys.contains(key) ? "old" : newKeys.contains(key) ? "new" : null;
                if (side == null) continue;
                long start = trees.getSourcePositions().getStartPosition(unit, declaration);
                declarations.add(new Declaration(
                    type.getSimpleName().toString(),
                    type.getQualifiedName().toString(),
                    relative(root, file),
                    line(unit, start),
                    side
                ));
            }
        }
        declarations.sort(Comparator.comparing(Declaration::qualifiedName));
        return declarations;
    }

    private static String authorityStatus(
        List<Declaration> oldDeclarations,
        List<Declaration> newDeclarations
    ) {
        if (oldDeclarations.size() > 1) return "ambiguous_old_authority";
        if (newDeclarations.isEmpty()) return "missing_new_authority";
        if (newDeclarations.size() > 1) return "ambiguous_new_authority";
        return "resolved";
    }

    private static void scanUnit(
        Path root,
        CompilationUnitTree unit,
        Path file,
        Trees trees,
        Set<String> oldKeys,
        Set<String> newKeys,
        Map<String, String> authorities,
        List<Occurrence> occurrences,
        List<DeferredReference> deferred
    ) {
        String label = relative(root, file);
        new TreePathScanner<Void, Void>() {
            @Override
            public Void visitIdentifier(IdentifierTree tree, Void unused) {
                recordOccurrence(tree, tree.getName().toString());
                return super.visitIdentifier(tree, unused);
            }

            @Override
            public Void visitMemberSelect(MemberSelectTree tree, Void unused) {
                recordOccurrence(tree, tree.getIdentifier().toString());
                return super.visitMemberSelect(tree, unused);
            }

            @Override
            public Void visitLiteral(LiteralTree tree, Void unused) {
                if (tree.getValue() instanceof String value && containsTerm(value, oldKeys, newKeys)) {
                    long start = trees.getSourcePositions().getStartPosition(unit, tree);
                    String kind = literalKind(getCurrentPath());
                    deferred.add(new DeferredReference(
                        kind,
                        label,
                        line(unit, start),
                        abbreviate(value),
                        switch (kind) {
                            case "framework_annotation_reference" ->
                                "Annotation-mediated/framework interpretation is not compiler rename authority.";
                            case "reflection_string_reference" ->
                                "Reflection and dynamic references are deferred for human review.";
                            default -> "String and dynamic references are deferred for human review.";
                        }
                    ));
                }
                return super.visitLiteral(tree, unused);
            }

            private void recordOccurrence(Tree tree, String name) {
                String key = normalize(name);
                if (!oldKeys.contains(key) && !newKeys.contains(key)) return;
                Element element = trees.getElement(getCurrentPath());
                TypeElement owner = owningTopLevelType(element);
                String qualified = owner == null ? "" : owner.getQualifiedName().toString();
                String classification = authorities.get(qualified);
                if (classification == null) {
                    classification = element == null
                        ? "unresolved_identifier"
                        : "shadowed_or_unrelated_symbol";
                }
                long start = trees.getSourcePositions().getStartPosition(unit, tree);
                occurrences.add(new Occurrence(
                    name,
                    label,
                    line(unit, start),
                    start,
                    classification,
                    syntax(getCurrentPath())
                ));
            }
        }.scan(unit, null);
    }

    private static TypeElement owningTopLevelType(Element element) {
        Element current = element;
        TypeElement result = null;
        while (current != null && !(current instanceof PackageElement)) {
            if (current instanceof TypeElement type) result = type;
            current = current.getEnclosingElement();
        }
        return result;
    }

    private static String syntax(TreePath path) {
        TreePath current = path;
        while (current != null) {
            if (current.getLeaf() instanceof ImportTree) return "import";
            current = current.getParentPath();
        }
        return path.getLeaf().getKind().name().toLowerCase(Locale.ROOT);
    }

    private static String literalKind(TreePath path) {
        TreePath current = path;
        while (current != null) {
            if (current.getLeaf() instanceof AnnotationTree) return "framework_annotation_reference";
            if (current.getLeaf() instanceof MethodInvocationTree invocation) {
                String method = invocation.getMethodSelect().toString();
                if (method.equals("Class.forName") || method.endsWith(".getMethod")
                    || method.endsWith(".getDeclaredMethod") || method.endsWith(".getField")
                    || method.endsWith(".getDeclaredField") || method.equals("ServiceLoader.load")) {
                    return "reflection_string_reference";
                }
            }
            current = current.getParentPath();
        }
        return "string_or_dynamic_reference";
    }

    private static boolean containsTerm(String text, Set<String> oldKeys, Set<String> newKeys) {
        String normalized = normalize(text);
        return oldKeys.stream().anyMatch(normalized::contains)
            || newKeys.stream().anyMatch(normalized::contains);
    }

    private static Set<String> normalized(List<String> terms) {
        Set<String> values = new LinkedHashSet<>();
        for (String term : terms) {
            String value = normalize(term);
            if (!value.isEmpty()) values.add(value);
        }
        return values;
    }

    private static String normalize(String value) {
        StringBuilder out = new StringBuilder();
        value.codePoints().filter(Character::isLetterOrDigit)
            .forEach(codepoint -> out.appendCodePoint(Character.toLowerCase(codepoint)));
        return out.toString();
    }

    private static boolean hasErrors(DiagnosticCollector<JavaFileObject> diagnostics) {
        return diagnostics.getDiagnostics().stream()
            .anyMatch(item -> item.getKind() == Diagnostic.Kind.ERROR);
    }

    private static Map<String, Object> diagnosticPayload(
        Options options,
        DiagnosticCollector<JavaFileObject> diagnostics,
        String kind
    ) {
        List<String> values = diagnostics.getDiagnostics().stream()
            .filter(item -> item.getKind() == Diagnostic.Kind.ERROR)
            .map(item -> diagnostic(options.root, item))
            .toList();
        return mapOf(
            "status", "failed",
            "reason", values.isEmpty() ? kind : values.get(0),
            "failure_kind", kind,
            "analyzer", "jdk-compiler-tree-type-api",
            "authority_status", "unavailable",
            "files", options.sources.stream().map(path -> relative(options.root, path)).toList(),
            "declarations", mapOf("old", List.of(), "new", List.of()),
            "occurrences", List.of(),
            "deferred_references", List.of(),
            "resolution_diagnostics", values
        );
    }

    private static String diagnostic(Path root, Diagnostic<? extends JavaFileObject> item) {
        String source = item.getSource() == null
            ? "<compiler>"
            : relative(root, Path.of(item.getSource().toUri()));
        return source + ":" + item.getLineNumber() + ": " + item.getMessage(Locale.ROOT);
    }

    private static List<Occurrence> deduplicateOccurrences(List<Occurrence> values) {
        Map<String, Occurrence> unique = new LinkedHashMap<>();
        values.stream().sorted(
            Comparator.comparing(Occurrence::file).thenComparingLong(Occurrence::start)
                .thenComparing(Occurrence::classification)
        ).forEach(value -> unique.put(
            value.file + ":" + value.start + ":" + value.classification, value
        ));
        return new ArrayList<>(unique.values());
    }

    private static List<DeferredReference> deduplicateDeferred(List<DeferredReference> values) {
        Map<String, DeferredReference> unique = new LinkedHashMap<>();
        values.stream().sorted(
            Comparator.comparing(DeferredReference::file).thenComparingInt(DeferredReference::line)
                .thenComparing(DeferredReference::kind)
        ).forEach(value -> unique.put(
            value.file + ":" + value.line + ":" + value.kind, value
        ));
        return new ArrayList<>(unique.values());
    }

    private static Map<String, Object> declarationMap(Declaration value) {
        return mapOf(
            "name", value.name,
            "qualified_name", value.qualifiedName,
            "file", value.file,
            "line", value.line,
            "authority", "public_top_level_type_element"
        );
    }

    private static Map<String, Object> occurrenceMap(Occurrence value) {
        return mapOf(
            "name", value.name,
            "file", value.file,
            "line", value.line,
            "classification", value.classification,
            "syntax", value.syntax
        );
    }

    private static Map<String, Object> deferredMap(DeferredReference value) {
        return mapOf(
            "kind", value.kind,
            "file", value.file,
            "line", value.line,
            "text", value.text,
            "reason", value.reason
        );
    }

    private static boolean traversesSymlink(Path root, Path path) {
        Path current = root;
        for (Path part : root.relativize(path)) {
            current = current.resolve(part);
            if (Files.exists(current, LinkOption.NOFOLLOW_LINKS) && Files.isSymbolicLink(current)) {
                return true;
            }
        }
        return false;
    }

    private static int line(CompilationUnitTree unit, long position) {
        return position < 0 ? 0 : Math.toIntExact(unit.getLineMap().getLineNumber(position));
    }

    private static String relative(Path root, Path path) {
        Path normalized = path.toAbsolutePath().normalize();
        return normalized.startsWith(root)
            ? root.relativize(normalized).toString().replace('\\', '/')
            : normalized.toString();
    }

    private static String abbreviate(String value) {
        String oneLine = value.replace('\n', ' ').replace('\r', ' ');
        return oneLine.length() <= 160 ? oneLine : oneLine.substring(0, 157) + "...";
    }

    private static String message(Exception error) {
        return error.getMessage() == null ? error.getClass().getSimpleName() : error.getMessage();
    }

    private static void writeAtomic(Path path, String contents) throws Exception {
        Files.createDirectories(path.getParent());
        Path temporary = path.resolveSibling(path.getFileName() + ".tmp-" + ProcessHandle.current().pid());
        Files.writeString(temporary, contents, StandardCharsets.UTF_8);
        try {
            Files.move(
                temporary,
                path,
                StandardCopyOption.REPLACE_EXISTING,
                StandardCopyOption.ATOMIC_MOVE
            );
        } catch (java.nio.file.AtomicMoveNotSupportedException ignored) {
            Files.move(temporary, path, StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private static Outcome failed(Map<String, Object> payload) {
        return new Outcome(payload, 2);
    }

    private static Outcome unsupported(String reason) {
        return new Outcome(mapOf(
            "status", "unsupported",
            "reason", reason,
            "authority_status", "unavailable",
            "declarations", mapOf("old", List.of(), "new", List.of()),
            "occurrences", List.of(),
            "deferred_references", List.of(),
            "resolution_diagnostics", List.of()
        ), 0);
    }

    private static Map<String, Object> mapOf(Object... values) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index < values.length; index += 2) {
            result.put((String) values[index], values[index + 1]);
        }
        return result;
    }

    private static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof String text) return "\"" + escape(text) + "\"";
        if (value instanceof Number || value instanceof Boolean) return value.toString();
        if (value instanceof Map<?, ?> map) {
            List<String> fields = new ArrayList<>();
            for (var entry : map.entrySet()) {
                fields.add(json(String.valueOf(entry.getKey())) + ":" + json(entry.getValue()));
            }
            return "{" + String.join(",", fields) + "}";
        }
        if (value instanceof Iterable<?> iterable) {
            List<String> items = new ArrayList<>();
            for (Object item : iterable) items.add(json(item));
            return "[" + String.join(",", items) + "]";
        }
        throw new IllegalArgumentException("unsupported JSON value: " + value.getClass());
    }

    private static String escape(String value) {
        StringBuilder out = new StringBuilder();
        for (char character : value.toCharArray()) {
            switch (character) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (character < 0x20) out.append(String.format("\\u%04x", (int) character));
                    else out.append(character);
                }
            }
        }
        return out.toString();
    }

    private static final class Outcome extends Exception {
        final Map<String, Object> payload;
        final int exit;

        Outcome(Map<String, Object> payload, int exit) {
            this.payload = payload;
            this.exit = exit;
        }
    }
}

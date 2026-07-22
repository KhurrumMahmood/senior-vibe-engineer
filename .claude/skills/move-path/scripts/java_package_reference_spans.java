// Emit exact Java package/import/FQCN spans for one reviewed leaf-package move.
// The host JDK compiler must parse and attribute every eligible first-party
// source before a span is considered safe to rewrite.
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.ImportTree;
import com.sun.source.tree.MemberSelectTree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.TreePath;
import com.sun.source.util.TreePathScanner;
import com.sun.source.util.Trees;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.attribute.BasicFileAttributes;
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
import javax.lang.model.element.PackageElement;
import javax.lang.model.element.TypeElement;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

class JavaPackageReferenceSpans {
    private static final Set<String> SKIP_PARTS = Set.of(
        ".git", ".venv", "venv", "build", "dist", "generated", "gen",
        "vendor", "target", "node_modules", "reports"
    );

    private record Options(Path root, Path from, Path to) {}
    private record Span(
        String file,
        long start,
        long end,
        int line,
        String oldText,
        String newText,
        String kind
    ) {}

    public static void main(String[] args) {
        Map<String, Object> result;
        int exit = 0;
        try {
            result = run(parseArgs(args));
        } catch (Outcome outcome) {
            result = outcome.payload;
            exit = outcome.exit;
        } catch (Exception error) {
            result = mapOf(
                "status", "failed",
                "error", error.getMessage() == null ? error.getClass().getSimpleName() : error.getMessage(),
                "blocked", List.of(),
                "spans", List.of()
            );
            exit = 2;
        }
        System.out.println(json(result));
        if (exit != 0) System.exit(exit);
    }

    private static Options parseArgs(String[] args) throws Outcome {
        Map<String, String> values = new HashMap<>();
        if (args.length % 2 != 0) throw failed("invalid arguments");
        for (int index = 0; index < args.length; index += 2) {
            if (!Set.of("--project-root", "--from", "--to").contains(args[index])
                || values.put(args[index], args[index + 1]) != null) {
                throw failed("invalid arguments");
            }
        }
        for (String required : List.of("--project-root", "--from", "--to")) {
            if (!values.containsKey(required)) throw failed("missing argument: " + required);
        }
        Path root = Path.of(values.get("--project-root")).toAbsolutePath().normalize();
        Path from = inside(root, values.get("--from"));
        Path to = inside(root, values.get("--to"));
        return new Options(root, from, to);
    }

    private static Path inside(Path root, String supplied) throws Outcome {
        Path candidate = Path.of(supplied);
        if (!candidate.isAbsolute()) candidate = root.resolve(candidate);
        candidate = candidate.toAbsolutePath().normalize();
        if (!candidate.startsWith(root)) throw failed("path escapes project root: " + supplied);
        return candidate;
    }

    private static Map<String, Object> run(Options options) throws Exception {
        if (Runtime.version().feature() < 17) {
            throw unsupported("java_version_too_old", "Java 17 or newer is required.");
        }
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) throw unsupported("javac_tool_missing", "A full JDK is required.");
        if (!Files.isDirectory(options.from, LinkOption.NOFOLLOW_LINKS)) {
            throw unsupported("java_package_move_must_be_directory", "Source must be one package directory.");
        }

        List<Path> sources = collectSources(options.root);
        List<Path> movedSources = sources.stream().filter(path -> path.getParent().equals(options.from)).toList();
        if (movedSources.isEmpty()) throw unsupported("java_package_source_missing", "Package has no Java sources.");

        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        List<CompilationUnitTree> units = new ArrayList<>();
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(diagnostics, Locale.ROOT, StandardCharsets.UTF_8)) {
            JavacTask task = (JavacTask) compiler.getTask(
                null,
                manager,
                diagnostics,
                List.of("--release", "17", "-proc:none"),
                null,
                manager.getJavaFileObjectsFromPaths(sources)
            );
            task.parse().forEach(units::add);
            if (hasErrors(diagnostics)) throw failed(firstDiagnostic(options.root, diagnostics));
            task.analyze();
            if (hasErrors(diagnostics)) {
                throw partial("java_unresolved_compilation", firstDiagnostic(options.root, diagnostics));
            }
            Trees trees = Trees.instance(task);
            Map<URI, Path> paths = new HashMap<>();
            for (Path source : sources) paths.put(source.toUri(), source);

            String oldPackage = packageIdentity(units, paths, movedSources);
            Path sourceRoot = sourceRoot(options.from, oldPackage);
            if (!options.to.startsWith(sourceRoot) || options.to.equals(sourceRoot)) {
                throw unsupported("java_source_root_changed", "Destination must remain under the same Java source root.");
            }
            String newPackage = packageFromPath(sourceRoot.relativize(options.to));
            if (newPackage.equals(oldPackage)) {
                throw unsupported("java_package_identity_unchanged", "Destination does not change the package identity.");
            }

            Set<Path> moved = Set.copyOf(movedSources);
            List<Span> spans = new ArrayList<>();
            for (CompilationUnitTree unit : units) {
                Path file = paths.get(unit.getSourceFile().toUri());
                if (moved.contains(file)) {
                    long start = trees.getSourcePositions().getStartPosition(unit, unit.getPackageName());
                    long end = trees.getSourcePositions().getEndPosition(unit, unit.getPackageName());
                    spans.add(span(options.root, unit, file, start, end, oldPackage, newPackage, "java_package"));
                }
                scanReferences(options.root, unit, file, trees, oldPackage, newPackage, spans);
            }
            spans = deduplicate(spans);
            List<Map<String, Object>> blocked = dynamicOccurrences(options.root, sources, oldPackage, spans);
            String status = blocked.isEmpty() ? "complete" : "partial";
            return mapOf(
                "status", status,
                "analyzer", "jdk-compiler-tree-api",
                "minimum_jdk", 17,
                "old_package", oldPackage,
                "new_package", newPackage,
                "source_root", relative(options.root, sourceRoot),
                "moved_files", movedSources.stream().map(path -> relative(options.root, path)).toList(),
                "java_files", sources.stream().map(path -> relative(options.root, path)).toList(),
                "spans", spans.stream().map(JavaPackageReferenceSpans::spanMap).toList(),
                "blocked", blocked
            );
        }
    }

    private static List<Path> collectSources(Path root) throws Exception {
        List<Path> paths = new ArrayList<>();
        Files.walkFileTree(root, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) {
                if (!dir.equals(root) && (Files.isSymbolicLink(dir) || skipped(root, dir))) {
                    return FileVisitResult.SKIP_SUBTREE;
                }
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
                if (!Files.isSymbolicLink(file) && file.getFileName().toString().endsWith(".java")
                    && !skipped(root, file)) {
                    paths.add(file.toAbsolutePath().normalize());
                }
                return FileVisitResult.CONTINUE;
            }
        });
        paths.sort(Comparator.comparing(path -> relative(root, path)));
        return paths;
    }

    private static boolean skipped(Path root, Path path) {
        for (Path part : root.relativize(path.toAbsolutePath().normalize())) {
            if (SKIP_PARTS.contains(part.toString().toLowerCase(Locale.ROOT))) return true;
        }
        return false;
    }

    private static boolean hasErrors(DiagnosticCollector<JavaFileObject> diagnostics) {
        return diagnostics.getDiagnostics().stream().anyMatch(item -> item.getKind() == Diagnostic.Kind.ERROR);
    }

    private static String firstDiagnostic(Path root, DiagnosticCollector<JavaFileObject> diagnostics) {
        return diagnostics.getDiagnostics().stream()
            .filter(item -> item.getKind() == Diagnostic.Kind.ERROR)
            .findFirst()
            .map(item -> {
                String source = item.getSource() == null ? "<compiler>" : relative(root, Path.of(item.getSource().toUri()));
                return source + ":" + item.getLineNumber() + ": " + item.getMessage(Locale.ROOT);
            })
            .orElse("Java compilation evidence is incomplete.");
    }

    private static String packageIdentity(
        List<CompilationUnitTree> units,
        Map<URI, Path> paths,
        List<Path> movedSources
    ) throws Outcome {
        Set<Path> moved = Set.copyOf(movedSources);
        Set<String> packages = new LinkedHashSet<>();
        for (CompilationUnitTree unit : units) {
            if (moved.contains(paths.get(unit.getSourceFile().toUri()))) {
                packages.add(unit.getPackageName() == null ? "" : unit.getPackageName().toString());
            }
        }
        if (packages.size() != 1 || packages.contains("")) {
            throw unsupported("java_mixed_or_default_package", "Source directory must declare exactly one named package.");
        }
        return packages.iterator().next();
    }

    private static Path sourceRoot(Path from, String packageName) throws Outcome {
        Path root = from;
        String[] parts = packageName.split("\\.");
        for (int index = parts.length - 1; index >= 0; index--) {
            if (root.getFileName() == null || !root.getFileName().toString().equals(parts[index])) {
                throw unsupported("java_package_path_mismatch", "Package declaration does not match its source path.");
            }
            root = root.getParent();
        }
        return root;
    }

    private static String packageFromPath(Path relative) throws Outcome {
        List<String> parts = new ArrayList<>();
        for (Path part : relative) {
            String value = part.toString();
            if (!Character.isJavaIdentifierStart(value.charAt(0))
                || value.chars().skip(1).anyMatch(character -> !Character.isJavaIdentifierPart(character))) {
                throw unsupported("java_destination_not_package", "Destination is not a valid Java package path.");
            }
            parts.add(value);
        }
        return String.join(".", parts);
    }

    private static void scanReferences(
        Path root,
        CompilationUnitTree unit,
        Path file,
        Trees trees,
        String oldPackage,
        String newPackage,
        List<Span> spans
    ) {
        new TreePathScanner<Void, Void>() {
            @Override
            public Void visitImport(ImportTree tree, Void unused) {
                String oldText = tree.getQualifiedIdentifier().toString();
                Element element = trees.getElement(new TreePath(getCurrentPath(), tree.getQualifiedIdentifier()));
                if (belongsTo(element, oldPackage)
                    || oldText.equals(oldPackage + ".*")
                    || (tree.isStatic() && oldText.startsWith(oldPackage + "."))) {
                    long start = trees.getSourcePositions().getStartPosition(unit, tree.getQualifiedIdentifier());
                    long end = trees.getSourcePositions().getEndPosition(unit, tree.getQualifiedIdentifier());
                    spans.add(span(root, unit, file, start, end, oldText, replacePrefix(oldText, oldPackage, newPackage), "java_import"));
                }
                return null;
            }

            @Override
            public Void visitMemberSelect(MemberSelectTree tree, Void unused) {
                Element element = trees.getElement(getCurrentPath());
                if (element instanceof TypeElement type) {
                    String qualified = type.getQualifiedName().toString();
                    if (packageName(type).equals(oldPackage) && tree.toString().equals(qualified)) {
                        long start = trees.getSourcePositions().getStartPosition(unit, tree);
                        long end = trees.getSourcePositions().getEndPosition(unit, tree);
                        spans.add(span(root, unit, file, start, end, qualified, replacePrefix(qualified, oldPackage, newPackage), "java_fully_qualified_type"));
                        return null;
                    }
                }
                return super.visitMemberSelect(tree, unused);
            }
        }.scan(unit, null);
    }

    private static boolean belongsTo(Element element, String packageName) {
        if (element == null) return false;
        Element cursor = element;
        while (cursor != null && !(cursor instanceof PackageElement)) cursor = cursor.getEnclosingElement();
        return cursor instanceof PackageElement pkg && pkg.getQualifiedName().contentEquals(packageName);
    }

    private static String packageName(TypeElement type) {
        Element cursor = type.getEnclosingElement();
        while (cursor != null && !(cursor instanceof PackageElement)) cursor = cursor.getEnclosingElement();
        return cursor instanceof PackageElement pkg ? pkg.getQualifiedName().toString() : "";
    }

    private static String replacePrefix(String value, String oldPackage, String newPackage) {
        return newPackage + value.substring(oldPackage.length());
    }

    private static Span span(
        Path root,
        CompilationUnitTree unit,
        Path file,
        long start,
        long end,
        String oldText,
        String newText,
        String kind
    ) {
        int line = start < 0 ? 0 : Math.toIntExact(unit.getLineMap().getLineNumber(start));
        return new Span(relative(root, file), start, end, line, oldText, newText, kind);
    }

    private static List<Span> deduplicate(List<Span> spans) {
        Map<String, Span> unique = new LinkedHashMap<>();
        spans.stream()
            .sorted(Comparator.comparing(Span::file).thenComparingLong(Span::start).thenComparing(Span::kind))
            .forEach(span -> unique.put(span.file + ":" + span.start + ":" + span.end, span));
        return new ArrayList<>(unique.values());
    }

    private static List<Map<String, Object>> dynamicOccurrences(
        Path root,
        List<Path> sources,
        String oldPackage,
        List<Span> spans
    ) throws Exception {
        Map<String, List<Span>> byFile = new HashMap<>();
        for (Span span : spans) byFile.computeIfAbsent(span.file, ignored -> new ArrayList<>()).add(span);
        List<Map<String, Object>> blocked = new ArrayList<>();
        for (Path source : sources) {
            String file = relative(root, source);
            String text = Files.readString(source, StandardCharsets.UTF_8);
            int offset = text.indexOf(oldPackage);
            while (offset >= 0) {
                int found = offset;
                boolean covered = byFile.getOrDefault(file, List.of()).stream()
                    .anyMatch(span -> found >= span.start && found < span.end);
                if (!covered) {
                    int line = 1 + Math.toIntExact(text.substring(0, offset).chars().filter(character -> character == '\n').count());
                    blocked.add(mapOf("kind", "java_dynamic_old_package", "path", file, "line", line));
                }
                offset = text.indexOf(oldPackage, offset + oldPackage.length());
            }
        }
        return blocked;
    }

    private static Map<String, Object> spanMap(Span span) {
        return mapOf(
            "file", span.file,
            "start", span.start,
            "end", span.end,
            "line", span.line,
            "old_text", span.oldText,
            "new_text", span.newText,
            "kind", span.kind
        );
    }

    private static Outcome failed(String message) {
        return new Outcome(mapOf("status", "failed", "error", message, "blocked", List.of(), "spans", List.of()), 2);
    }

    private static Outcome partial(String kind, String message) {
        return new Outcome(mapOf(
            "status", "partial", "error", message,
            "blocked", List.of(mapOf("kind", kind, "detail", message)), "spans", List.of()
        ), 0);
    }

    private static Outcome unsupported(String kind, String message) {
        return new Outcome(mapOf(
            "status", "unsupported", "error", message,
            "blocked", List.of(mapOf("kind", kind, "detail", message)), "spans", List.of()
        ), 0);
    }

    private static String relative(Path root, Path path) {
        return root.relativize(path.toAbsolutePath().normalize()).toString().replace('\\', '/');
    }

    private static Map<String, Object> mapOf(Object... values) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index < values.length; index += 2) result.put((String) values[index], values[index + 1]);
        return result;
    }

    private static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof String text) return "\"" + escape(text) + "\"";
        if (value instanceof Number || value instanceof Boolean) return value.toString();
        if (value instanceof Map<?, ?> map) {
            List<String> fields = new ArrayList<>();
            for (var entry : map.entrySet()) fields.add(json(String.valueOf(entry.getKey())) + ":" + json(entry.getValue()));
            return "{" + String.join(",", fields) + "}";
        }
        if (value instanceof Iterable<?> iterable) {
            List<String> items = new ArrayList<>();
            for (Object item : iterable) items.add(json(item));
            return "[" + String.join(",", items) + "]";
        }
        throw new IllegalArgumentException("unsupported JSON value: " + value.getClass());
    }

    private static String escape(String text) {
        return text.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r");
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

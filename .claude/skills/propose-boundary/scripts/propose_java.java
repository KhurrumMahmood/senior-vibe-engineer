// Produce a conservative, read-only Java boundary proposal from JDK compiler facts.
//
// Java source-file mode keeps the copied closure to this file plus the host JDK.
// The compiler parses and attributes every eligible production source before any
// import or fully-qualified reference is reported as resolved.
import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.ImportTree;
import com.sun.source.tree.MemberSelectTree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.TreePath;
import com.sun.source.util.TreePathScanner;
import com.sun.source.util.Trees;

import java.io.IOException;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.attribute.BasicFileAttributes;
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
import java.util.TreeMap;
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

class ProposeJava {
    private static final Set<String> EXCLUDED = Set.of(
        ".git", ".venv", "venv", "build", "dist", "generated", "gen",
        "vendor", "target", "test", "tests", "fixtures", "fixture", "reports"
    );

    private record Options(
        Path root,
        Path target,
        Path inspection,
        Path proposal,
        int candidates,
        int minimumJdk
    ) {}

    private record Symbol(String name, String file, int line, boolean isPublic, String domain) {}

    private record Impact(
        String callerPackage,
        String file,
        int line,
        String referencedType,
        String style,
        String resolution
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
        } catch (Terminal terminal) {
            try {
                writeTerminal(options, terminal);
            } catch (IOException writeError) {
                System.err.println(writeError.getMessage());
                System.exit(2);
                return;
            }
            exit = terminal.exit;
        } catch (Exception error) {
            try {
                writeTerminal(options, new Terminal(
                    "failed", "defer_internal_error", "internal_error", error.getMessage(), 2
                ));
            } catch (IOException ignored) {
                // The original error remains the most useful failure.
            }
            System.err.println("[propose_java] " + error.getMessage());
            exit = 2;
        }
        if (exit != 0) System.exit(exit);
    }

    private static Options parseArgs(String[] args) {
        Map<String, String> values = new HashMap<>();
        Set<String> allowed = Set.of(
            "--target", "--project-root", "--inspection", "--proposal",
            "--candidates", "--minimum-jdk"
        );
        if (args.length % 2 != 0) throw usage();
        for (int index = 0; index < args.length; index += 2) {
            if (!allowed.contains(args[index]) || values.put(args[index], args[index + 1]) != null) {
                throw usage();
            }
        }
        for (String required : List.of("--target", "--project-root", "--inspection", "--proposal")) {
            if (!values.containsKey(required)) throw usage();
        }
        Path root = Path.of(values.get("--project-root")).toAbsolutePath().normalize();
        Path target = resolveInside(root, values.get("--target"), "target");
        Path inspection = resolveInside(root, values.get("--inspection"), "inspection");
        Path proposal = resolveInside(root, values.get("--proposal"), "proposal");
        Path reportRoot = root.resolve("reports/propose-boundary");
        if (!inspection.startsWith(reportRoot) || inspection.equals(reportRoot)
            || !proposal.startsWith(reportRoot) || proposal.equals(reportRoot)) {
            throw new IllegalArgumentException("artifacts must stay below reports/propose-boundary");
        }
        int candidates = positiveInt(values.getOrDefault("--candidates", "1"), "--candidates");
        int minimumJdk = positiveInt(values.getOrDefault("--minimum-jdk", "17"), "--minimum-jdk");
        return new Options(root, target, inspection, proposal, candidates, minimumJdk);
    }

    private static IllegalArgumentException usage() {
        return new IllegalArgumentException(
            "usage: propose_java.java --target <package-dir> --project-root <root> "
                + "--inspection <inspection.json> --proposal <proposal.md> [--candidates N]"
        );
    }

    private static int positiveInt(String raw, String flag) {
        try {
            int value = Integer.parseInt(raw);
            if (value > 0) return value;
        } catch (NumberFormatException ignored) {
            // Fall through to the stable CLI error.
        }
        throw new IllegalArgumentException(flag + " must be a positive integer");
    }

    private static Path resolveInside(Path root, String supplied, String label) {
        Path candidate = Path.of(supplied);
        if (!candidate.isAbsolute()) candidate = root.resolve(candidate);
        candidate = candidate.toAbsolutePath().normalize();
        if (!candidate.startsWith(root)) {
            throw new IllegalArgumentException(label + " must stay inside project root: " + supplied);
        }
        return candidate;
    }

    private static void run(Options options) throws Exception {
        int feature = Runtime.version().feature();
        if (feature < options.minimumJdk) {
            throw new Terminal(
                "unsupported", "defer_jdk_version", "jdk_version_too_old",
                "JDK " + feature + " is below required JDK " + options.minimumJdk + ".", 0
            );
        }
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) {
            throw new Terminal(
                "unsupported", "defer_tool_missing", "javac_tool_missing",
                "A full JDK with javac is required.", 0
            );
        }
        if (!Files.isDirectory(options.root, LinkOption.NOFOLLOW_LINKS)) {
            throw new Terminal("unsupported", "defer_project_root", "project_root_missing", "Project root is not a directory.", 0);
        }
        if (traversesSymlink(options.root, options.target)) {
            throw new Terminal("unsupported", "defer_unsafe_target", "symlink_target", "Target must not traverse a symbolic link.", 0);
        }
        if (!Files.isDirectory(options.target, LinkOption.NOFOLLOW_LINKS)) {
            throw new Terminal("unsupported", "defer_target_not_found", "target_not_directory", "Target must be one Java package directory.", 0);
        }
        if (excluded(options.root, options.target)) {
            throw new Terminal("unsupported", "defer_excluded_target", "excluded_target", "Generated, vendor, test, and build targets are outside Java proposal v1.", 0);
        }

        List<Path> sources = collectSources(options.root);
        List<Path> targetSources = sources.stream()
            .filter(path -> path.getParent().equals(options.target))
            .toList();
        if (targetSources.isEmpty()) {
            throw new Terminal("unsupported", "defer_no_source", "no_eligible_java_source", "Target contains no eligible production Java source.", 0);
        }

        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        List<CompilationUnitTree> units = new ArrayList<>();
        Trees trees;
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(diagnostics, Locale.ROOT, StandardCharsets.UTF_8)) {
            Iterable<? extends JavaFileObject> files = manager.getJavaFileObjectsFromPaths(sources);
            JavacTask task = (JavacTask) compiler.getTask(
                null, manager, diagnostics, List.of("--release", "17", "-proc:none"), null, files
            );
            task.parse().forEach(units::add);
            if (hasErrors(diagnostics)) throw syntaxFailure(options.root, diagnostics);
            task.analyze();
            if (hasErrors(diagnostics)) throw resolutionFailure(options.root, diagnostics);
            trees = Trees.instance(task);

            Map<URI, Path> paths = new HashMap<>();
            for (Path path : sources) paths.put(path.toUri(), path);
            String targetPackage = packageForTarget(units, paths, targetSources);
            List<Symbol> symbols = targetSymbols(units, paths, targetSources, trees, options.root);
            List<Impact> impacts = callerImpacts(units, paths, trees, options.root, targetPackage, symbols);
            Map<String, Object> payload = successfulPayload(options, feature, targetPackage, symbols, impacts);
            writeArtifacts(options, payload);
        }
    }

    private static List<Path> collectSources(Path root) throws IOException {
        List<Path> paths = new ArrayList<>();
        Files.walkFileTree(root, Set.of(), Integer.MAX_VALUE, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) {
                if (!dir.equals(root) && (Files.isSymbolicLink(dir) || excluded(root, dir))) {
                    return FileVisitResult.SKIP_SUBTREE;
                }
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                if (!Files.isSymbolicLink(file) && file.getFileName().toString().endsWith(".java")
                    && !excluded(root, file) && !generated(file)) {
                    paths.add(file.toAbsolutePath().normalize());
                }
                return FileVisitResult.CONTINUE;
            }
        });
        paths.sort(Comparator.comparing(path -> relative(root, path)));
        return paths;
    }

    private static boolean generated(Path path) throws IOException {
        return Files.readAllLines(path, StandardCharsets.UTF_8).stream().limit(5)
            .anyMatch(line -> line.contains("Generated") && line.contains("DO NOT EDIT"));
    }

    private static boolean excluded(Path root, Path path) {
        Path relative = root.relativize(path.toAbsolutePath().normalize());
        for (Path part : relative) {
            if (EXCLUDED.contains(part.toString().toLowerCase(Locale.ROOT))) return true;
        }
        String name = path.getFileName().toString().toLowerCase(Locale.ROOT);
        return name.endsWith("test.java") || name.endsWith("tests.java") || name.endsWith("generated.java");
    }

    private static boolean traversesSymlink(Path root, Path candidate) throws IOException {
        Path current = root;
        if (Files.isSymbolicLink(root)) return true;
        for (Path part : root.relativize(candidate)) {
            current = current.resolve(part);
            if (Files.exists(current, LinkOption.NOFOLLOW_LINKS) && Files.isSymbolicLink(current)) return true;
        }
        return false;
    }

    private static boolean hasErrors(DiagnosticCollector<JavaFileObject> diagnostics) {
        return diagnostics.getDiagnostics().stream().anyMatch(item -> item.getKind() == Diagnostic.Kind.ERROR);
    }

    private static Terminal syntaxFailure(Path root, DiagnosticCollector<JavaFileObject> diagnostics) {
        return new Terminal("failed", "defer_syntax_error", "syntax_error", firstDiagnostic(root, diagnostics), 2);
    }

    private static Terminal resolutionFailure(Path root, DiagnosticCollector<JavaFileObject> diagnostics) {
        return new Terminal("partial", "defer_unresolved_compilation", "unresolved_compilation", firstDiagnostic(root, diagnostics), 0);
    }

    private static String firstDiagnostic(Path root, DiagnosticCollector<JavaFileObject> diagnostics) {
        return diagnostics.getDiagnostics().stream()
            .filter(item -> item.getKind() == Diagnostic.Kind.ERROR)
            .findFirst()
            .map(item -> {
                String source = item.getSource() == null ? "<compiler>" : relative(root, Path.of(item.getSource().toUri()));
                return source + ":" + item.getLineNumber() + ": " + item.getMessage(Locale.ROOT);
            })
            .orElse("Java compiler evidence is incomplete.");
    }

    private static String packageForTarget(
        List<CompilationUnitTree> units,
        Map<URI, Path> paths,
        List<Path> targetSources
    ) throws Terminal {
        Set<Path> targets = Set.copyOf(targetSources);
        Set<String> packages = new LinkedHashSet<>();
        for (CompilationUnitTree unit : units) {
            if (targets.contains(paths.get(unit.getSourceFile().toUri()))) {
                packages.add(unit.getPackageName() == null ? "" : unit.getPackageName().toString());
            }
        }
        if (packages.size() != 1 || packages.contains("")) {
            throw new Terminal("unsupported", "defer_package_topology", "mixed_or_default_package", "Target must declare exactly one named Java package.", 0);
        }
        return packages.iterator().next();
    }

    private static List<Symbol> targetSymbols(
        List<CompilationUnitTree> units,
        Map<URI, Path> paths,
        List<Path> targetSources,
        Trees trees,
        Path root
    ) {
        Set<Path> targets = Set.copyOf(targetSources);
        List<Symbol> symbols = new ArrayList<>();
        for (CompilationUnitTree unit : units) {
            Path path = paths.get(unit.getSourceFile().toUri());
            if (!targets.contains(path)) continue;
            for (var declaration : unit.getTypeDecls()) {
                if (!(declaration instanceof ClassTree type)) continue;
                String name = type.getSimpleName().toString();
                long position = trees.getSourcePositions().getStartPosition(unit, type);
                long line = position < 0 ? 0 : unit.getLineMap().getLineNumber(position);
                symbols.add(new Symbol(
                    name,
                    relative(root, path),
                    Math.toIntExact(line),
                    type.getModifiers().getFlags().contains(Modifier.PUBLIC),
                    leadingDomain(name)
                ));
            }
        }
        symbols.sort(Comparator.comparing(Symbol::name));
        return symbols;
    }

    private static List<Impact> callerImpacts(
        List<CompilationUnitTree> units,
        Map<URI, Path> paths,
        Trees trees,
        Path root,
        String targetPackage,
        List<Symbol> symbols
    ) {
        Set<String> targetTypes = new LinkedHashSet<>();
        for (Symbol symbol : symbols) targetTypes.add(targetPackage + "." + symbol.name);
        Map<String, Impact> impacts = new TreeMap<>();
        for (CompilationUnitTree unit : units) {
            String callerPackage = unit.getPackageName() == null ? "" : unit.getPackageName().toString();
            if (callerPackage.equals(targetPackage)) continue;
            Path file = paths.get(unit.getSourceFile().toUri());
            new TreePathScanner<Void, Void>() {
                @Override
                public Void visitImport(ImportTree tree, Void unused) {
                    Element element = trees.getElement(
                        new TreePath(getCurrentPath(), tree.getQualifiedIdentifier())
                    );
                    String qualified = element instanceof TypeElement type ? type.getQualifiedName().toString() : "";
                    if (targetTypes.contains(qualified)) add(tree, qualified, "import");
                    return super.visitImport(tree, unused);
                }

                @Override
                public Void visitMemberSelect(MemberSelectTree tree, Void unused) {
                    Element element = trees.getElement(getCurrentPath());
                    if (element instanceof TypeElement type) {
                        String qualified = type.getQualifiedName().toString();
                        if (targetTypes.contains(qualified) && tree.toString().equals(qualified)) {
                            add(tree, qualified, "fully-qualified");
                        }
                    }
                    return super.visitMemberSelect(tree, unused);
                }

                private void add(com.sun.source.tree.Tree tree, String qualified, String style) {
                    long start = trees.getSourcePositions().getStartPosition(unit, tree);
                    int line = start < 0 ? 0 : Math.toIntExact(unit.getLineMap().getLineNumber(start));
                    Impact impact = new Impact(
                        callerPackage, relative(root, file), line, qualified, style, "compiler-resolved"
                    );
                    impacts.put(impact.file + ":" + impact.line + ":" + style + ":" + qualified, impact);
                }
            }.scan(unit, null);
        }
        return new ArrayList<>(impacts.values());
    }

    private static Map<String, Object> successfulPayload(
        Options options,
        int feature,
        String targetPackage,
        List<Symbol> symbols,
        List<Impact> impacts
    ) {
        Map<String, List<Symbol>> domains = new TreeMap<>();
        for (Symbol symbol : symbols) {
            if (symbol.domain.length() >= 3) domains.computeIfAbsent(symbol.domain, ignored -> new ArrayList<>()).add(symbol);
        }
        List<Map<String, Object>> ranked = new ArrayList<>();
        for (var entry : domains.entrySet()) {
            if (entry.getValue().size() < 2) continue;
            List<String> members = entry.getValue().stream().map(Symbol::name).sorted().toList();
            List<String> publicApi = entry.getValue().stream().filter(Symbol::isPublic).map(Symbol::name).sorted().toList();
            ranked.add(mapOf(
                "cluster_id", entry.getKey(),
                "members", members,
                "proposed_public_api", publicApi,
                "rationale", members.size() + " top-level types share the " + entry.getKey() + " domain token in one Java package.",
                "scores", mapOf("named_member_count", members.size(), "combined", members.size())
            ));
        }
        ranked.sort((left, right) -> {
            int score = Integer.compare(score(right), score(left));
            return score != 0 ? score : ((String) left.get("cluster_id")).compareTo((String) right.get("cluster_id"));
        });
        List<Map<String, Object>> selected = new ArrayList<>();
        List<Map<String, Object>> omitted = new ArrayList<>();
        int cutoff = 0;
        if (!ranked.isEmpty()) {
            cutoff = score(ranked.get(Math.min(options.candidates - 1, ranked.size() - 1)));
            for (Map<String, Object> seam : ranked) {
                if (score(seam) >= cutoff) selected.add(seam);
                else omitted.add(mapOf("cluster_id", seam.get("cluster_id"), "score", score(seam)));
            }
        }

        String recommendation = selected.size() >= 2 ? "refactor" : "defer_no_seam";
        Map<String, Object> payload = mapOf(
            "schema_version", 1,
            "status", "complete",
            "recommendation", recommendation,
            "analyzer", "jdk-compiler-tree-api",
            "tooling", mapOf(
                "java_version", Runtime.version().toString(),
                "jdk_feature", feature,
                "minimum_jdk", options.minimumJdk,
                "resolution", "JavacTask.parse+analyze --release 17 -proc:none"
            ),
            "target", mapOf("path", relative(options.root, options.target), "package", targetPackage),
            "symbols", symbols.stream().map(ProposeJava::symbolMap).toList(),
            "caller_impact", impacts.stream().map(ProposeJava::impactMap).toList(),
            "candidate_selection", mapOf(
                "requested", options.candidates,
                "eligible", ranked.size(),
                "returned", selected.size(),
                "cutoff_score", cutoff,
                "ties_included", selected.size() > options.candidates,
                "omitted_count", omitted.size(),
                "omitted", omitted
            ),
            "candidate_seams", selected,
            "defer_signals", recommendation.equals("refactor") ? List.of() : List.of("single_cluster_no_seam")
        );
        return payload;
    }

    private static int score(Map<String, Object> seam) {
        return (Integer) ((Map<?, ?>) seam.get("scores")).get("combined");
    }

    private static Map<String, Object> symbolMap(Symbol symbol) {
        return mapOf(
            "name", symbol.name,
            "file", symbol.file,
            "line", symbol.line,
            "public", symbol.isPublic,
            "domain", symbol.domain
        );
    }

    private static Map<String, Object> impactMap(Impact impact) {
        return mapOf(
            "caller_package", impact.callerPackage,
            "file", impact.file,
            "line", impact.line,
            "referenced_type", impact.referencedType,
            "style", impact.style,
            "resolution", impact.resolution
        );
    }

    private static void writeTerminal(Options options, Terminal terminal) throws IOException {
        Map<String, Object> payload = mapOf(
            "schema_version", 1,
            "status", terminal.status,
            "recommendation", terminal.recommendation,
            "failure_kind", terminal.kind,
            "message", terminal.getMessage(),
            "analyzer", "jdk-compiler-tree-api",
            "target", mapOf("path", relative(options.root, options.target)),
            "candidate_seams", List.of(),
            "caller_impact", List.of()
        );
        writeArtifacts(options, payload);
        System.err.println("[propose_java] " + terminal.getMessage());
    }

    private static void writeArtifacts(Options options, Map<String, Object> payload) throws IOException {
        writeAtomic(options.inspection, json(payload) + "\n");
        writeAtomic(options.proposal, renderProposal(payload));
        System.out.println("wrote " + relative(options.root, options.inspection) + " and "
            + relative(options.root, options.proposal) + " (" + payload.get("recommendation") + ")");
    }

    private static String renderProposal(Map<String, Object> payload) {
        @SuppressWarnings("unchecked")
        Map<String, Object> target = (Map<String, Object>) payload.get("target");
        String path = String.valueOf(target.get("path"));
        String status = String.valueOf(payload.get("status"));
        String recommendation = String.valueOf(payload.get("recommendation"));
        StringBuilder out = new StringBuilder();
        out.append("# Boundary proposal — ").append(path).append("\n\n")
            .append("> **Detected by:** `/propose-boundary` Java v1 (read-only; no edits applied)\n")
            .append("> **Executed by:** `/refactor-subsystem` only after human approval.\n\n")
            .append("Recommendation: **").append(recommendation).append("**\n\n");
        if (!status.equals("complete") || !recommendation.equals("refactor")) {
            out.append("## Stop condition\n\nNo extraction proposal is safe: ")
                .append(payload.getOrDefault("message", "the package has no second viable named type domain"))
                .append(". Resolve the compiler, package, or evidence constraint and rerun.\n");
            return out.toString();
        }
        out.append("## Native Java evidence\n\n")
            .append("- JDK compiler-tree API: `JavacTask.parse()` plus `analyze()`.\n")
            .append("- Native verification after an approved move: `javac --release 17 -d <classes> <sources>`.\n")
            .append("- Annotation processing is disabled; no Maven, Gradle, language server, or third-party parser is used.\n\n")
            .append("## Candidate seams\n\n");
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> seams = (List<Map<String, Object>>) payload.get("candidate_seams");
        for (Map<String, Object> seam : seams) {
            out.append("### ").append(seam.get("cluster_id")).append(" (score: ")
                .append(score(seam)).append(")\n\n")
                .append("- Members: `").append(String.join("`, `", stringList(seam.get("members")))).append("`\n")
                .append("- Proposed public API: `")
                .append(String.join("`, `", stringList(seam.get("proposed_public_api")))).append("`\n\n");
        }
        out.append("## Caller impact\n\n| Caller package | File | Type | Style | Evidence |\n")
            .append("|---|---|---|---|---|\n");
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> impacts = (List<Map<String, Object>>) payload.get("caller_impact");
        for (Map<String, Object> impact : impacts) {
            out.append("| `").append(impact.get("caller_package")).append("` | `")
                .append(impact.get("file")).append(":").append(impact.get("line")).append("` | `")
                .append(impact.get("referenced_type")).append("` | ")
                .append(impact.get("style")).append(" | ").append(impact.get("resolution")).append(" |\n");
        }
        out.append("\n## Compatibility and verification plan\n\n")
            .append("1. Preserve the old package with temporary forwarding types only for the human-approved public API.\n")
            .append("2. Add characterization tests for each selected public type and listed caller.\n")
            .append("3. Update compiler-resolved imports and fully-qualified type references in the reviewed refactor.\n")
            .append("4. Compile all eligible sources with `javac --release 17` and run the host's tests.\n\n")
            .append("## Stop condition\n\nEvery listed caller uses the approved boundary and native compilation remains green.\n");
        return out.toString();
    }

    private static List<String> stringList(Object value) {
        @SuppressWarnings("unchecked")
        List<Object> items = (List<Object>) value;
        return items.stream().map(String::valueOf).toList();
    }

    private static String leadingDomain(String name) {
        StringBuilder out = new StringBuilder();
        for (int index = 0; index < name.length(); index++) {
            char current = name.charAt(index);
            if (index > 0 && Character.isUpperCase(current)) break;
            out.append(Character.toLowerCase(current));
        }
        return out.toString();
    }

    private static String relative(Path root, Path path) {
        Path normalized = path.toAbsolutePath().normalize();
        if (!normalized.startsWith(root)) return normalized.toString();
        return root.relativize(normalized).toString().replace('\\', '/');
    }

    private static void writeAtomic(Path path, String contents) throws IOException {
        Files.createDirectories(path.getParent());
        Path temporary = path.resolveSibling(path.getFileName() + ".tmp-" + ProcessHandle.current().pid());
        Files.writeString(temporary, contents, StandardCharsets.UTF_8);
        Files.move(temporary, path, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
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
        StringBuilder out = new StringBuilder();
        for (char character : text.toCharArray()) {
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

    private static final class Terminal extends Exception {
        final String status;
        final String recommendation;
        final String kind;
        final int exit;

        Terminal(String status, String recommendation, String kind, String message, int exit) {
            super(message);
            this.status = status;
            this.recommendation = recommendation;
            this.kind = kind;
            this.exit = exit;
        }
    }
}

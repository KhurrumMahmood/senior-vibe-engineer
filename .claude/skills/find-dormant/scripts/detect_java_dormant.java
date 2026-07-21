// Conservative Java dormant-code review using only the host JDK 17 compiler APIs.
// Run with: java detect_java_dormant.java --target ... --project-root ... --report-dir ...
// This file is intentionally self-contained so a copied skill has no repository runtime.
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.LiteralTree;
import com.sun.source.tree.MemberReferenceTree;
import com.sun.source.tree.MethodInvocationTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.util.JavacTask;
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
import java.nio.file.StandardCopyOption;
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
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.lang.model.element.Element;
import javax.lang.model.element.ElementKind;
import javax.lang.model.element.ExecutableElement;
import javax.lang.model.element.Modifier;
import javax.lang.model.element.TypeElement;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

class DetectJavaDormant {
    private static final Set<String> EXCLUDED = Set.of(
        ".git", ".gradle", ".idea", ".venv", "venv", "build", "coverage", "dist",
        "generated", "gen", "out", "target", "vendor", "test", "tests", "testfixtures",
        "fixtures", "reports", "node_modules"
    );
    private static final Pattern PACKAGE = Pattern.compile(
        "(?m)^\\s*package\\s+([A-Za-z_$][A-Za-z0-9_$.]*)\\s*;"
    );
    private static final Pattern GENERATED = Pattern.compile(
        "(?m)^\\s*@(javax\\.annotation\\.processing\\.)?Generated(?:\\s*\\(|\\s*$)"
    );

    private record Options(Path root, Path target, Path reportDir, int minimumJdk) {}
    private record Candidate(
        ExecutableElement element, String id, String file, int line, String name, String owner,
        int staticReferences
    ) {
        Candidate withStaticReferences(int count) {
            return new Candidate(element, id, file, line, name, owner, count);
        }
    }
    private record SourceScan(
        List<Path> eligible, List<String> generated, List<String> excluded, List<String> kotlin,
        List<String> symlinked
    ) {}
    private static final class Terminal extends Exception {
        private final String status;
        private final String kind;
        private final int exit;
        private final boolean write;

        Terminal(String status, String kind, String message, int exit, boolean write) {
            super(message);
            this.status = status;
            this.kind = kind;
            this.exit = exit;
            this.write = write;
        }

        String status() { return status; }
        String kind() { return kind; }
        int exit() { return exit; }
        boolean write() { return write; }
        String message() { return getMessage(); }
    }

    public static void main(String[] args) {
        Options options = null;
        try {
            options = parseArgs(args);
            validateArtifactPaths(options);
            Map<String, Object> payload = run(options);
            writeArtifacts(options, payload);
        } catch (Terminal terminal) {
            System.err.println("[detect_java_dormant] " + terminal.kind() + ": " + terminal.message());
            if (terminal.write() && options != null) {
                try {
                    writeArtifacts(options, terminalPayload(options, terminal));
                } catch (IOException writeError) {
                    System.err.println("[detect_java_dormant] " + writeError.getMessage());
                    System.exit(2);
                    return;
                }
            }
            if (terminal.exit() != 0) System.exit(terminal.exit());
        } catch (IllegalArgumentException error) {
            System.err.println(error.getMessage());
            System.exit(2);
        } catch (Exception error) {
            System.err.println("[detect_java_dormant] " + error.getMessage());
            System.exit(2);
        }
    }

    private static Options parseArgs(String[] args) {
        if (args.length % 2 != 0) throw usage();
        Map<String, String> values = new HashMap<>();
        Set<String> allowed = Set.of("--target", "--project-root", "--report-dir", "--minimum-jdk");
        for (int index = 0; index < args.length; index += 2) {
            if (!allowed.contains(args[index]) || values.put(args[index], args[index + 1]) != null) throw usage();
        }
        for (String required : List.of("--target", "--project-root", "--report-dir")) {
            if (!values.containsKey(required)) throw usage();
        }
        Path root = Path.of(values.get("--project-root")).toAbsolutePath().normalize();
        Path target = resolveInside(root, values.get("--target"), "target");
        Path reportDir = resolveInside(root, values.get("--report-dir"), "report directory");
        Path allowedReportRoot = root.resolve("reports/find-dormant");
        if (!reportDir.startsWith(allowedReportRoot) || reportDir.equals(allowedReportRoot)) {
            throw new IllegalArgumentException("report directory must stay below reports/find-dormant");
        }
        return new Options(root, target, reportDir, positiveInt(values.getOrDefault("--minimum-jdk", "17"), "--minimum-jdk"));
    }

    private static IllegalArgumentException usage() {
        return new IllegalArgumentException(
            "usage: detect_java_dormant.java --target <java-file-or-directory> --project-root <root> "
                + "--report-dir reports/find-dormant/<scan> [--minimum-jdk 17]"
        );
    }

    private static int positiveInt(String raw, String flag) {
        try {
            int value = Integer.parseInt(raw);
            if (value > 0) return value;
        } catch (NumberFormatException ignored) {
            // Stable CLI error below.
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

    private static void validateArtifactPaths(Options options) {
        if (Files.isSymbolicLink(options.root()) || traversesSymlink(options.root(), options.reportDir())) {
            throw new IllegalArgumentException("report directory must not traverse a symbolic link");
        }
        for (Path artifact : List.of(options.reportDir().resolve("findings.json"), options.reportDir().resolve("report.md"))) {
            if (!artifact.startsWith(options.reportDir())) {
                throw new IllegalArgumentException("artifact output must stay in the report directory");
            }
        }
    }

    private static Map<String, Object> run(Options options) throws Exception {
        int feature = Runtime.version().feature();
        if (feature < options.minimumJdk()) {
            throw new Terminal(
                "unsupported", "jdk_version_too_old",
                "JDK " + feature + " is below required JDK " + options.minimumJdk() + ".", 0, true
            );
        }
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) {
            throw new Terminal("unsupported", "javac_tool_missing", "A full JDK with javac is required.", 0, true);
        }
        if (!Files.isDirectory(options.root(), LinkOption.NOFOLLOW_LINKS)) {
            throw new Terminal("unsupported", "project_root_missing", "Project root is not a directory.", 0, true);
        }
        if (traversesSymlink(options.root(), options.target())) {
            throw new Terminal("unsupported", "unsafe_target", "Target must not traverse a symbolic link.", 0, true);
        }
        if (!Files.exists(options.target(), LinkOption.NOFOLLOW_LINKS)) {
            throw new Terminal("unsupported", "target_missing", "Target does not exist.", 0, true);
        }
        if (excluded(options.root(), options.target())) {
            throw new Terminal(
                "unsupported", "excluded_target",
                "Generated, vendor, test, and build targets are outside Java dormant v1.", 0, true
            );
        }

        List<Path> selected = selectedSources(options.root(), options.target());
        if (selected.isEmpty()) {
            throw new Terminal("unsupported", "no_eligible_java_source", "Target contains no eligible Java source.", 0, true);
        }
        for (Path source : selected) {
            if (Files.isSymbolicLink(source)) {
                throw new Terminal("unsupported", "unsafe_source", "Selected Java source must not be a symbolic link.", 0, true);
            }
        }
        Path sourceRoot = inferSourceRoot(options.root(), selected.get(0));
        SourceScan scan = collectSources(options.root(), sourceRoot);
        if (!scan.symlinked().isEmpty()) {
            throw new Terminal(
                "unsupported", "unsafe_source",
                "Java source root contains a symbolic-link source: " + scan.symlinked().get(0), 0, true
            );
        }
        Set<Path> selectedSet = new LinkedHashSet<>(selected);
        if (!scan.eligible().containsAll(selectedSet)) {
            throw new Terminal(
                "unsupported", "selected_source_unavailable",
                "Every selected source must be eligible, non-generated production Java.", 0, true
            );
        }

        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        List<CompilationUnitTree> units = new ArrayList<>();
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(
            diagnostics, Locale.ROOT, StandardCharsets.UTF_8
        )) {
            Iterable<? extends JavaFileObject> files = manager.getJavaFileObjectsFromPaths(scan.eligible());
            JavacTask task = (JavacTask) compiler.getTask(
                null, manager, diagnostics,
                List.of("--release", "17", "-proc:none", "--class-path", ""), null, files
            );
            task.parse().forEach(units::add);
            if (hasErrors(diagnostics)) {
                throw new Terminal("failed", "syntax_error", firstDiagnostic(options.root(), diagnostics), 2, false);
            }
            task.analyze();
            if (hasErrors(diagnostics)) {
                throw new Terminal(
                    "partial", "unresolved_compilation", firstDiagnostic(options.root(), diagnostics), 0, true
                );
            }

            Trees trees = Trees.instance(task);
            Map<URI, Path> paths = pathsByUri(scan.eligible());
            Map<ExecutableElement, Candidate> candidates = collectCandidates(
                units, paths, selectedSet, trees, options.root()
            );
            Map<ExecutableElement, Integer> references = new HashMap<>();
            for (ExecutableElement element : candidates.keySet()) references.put(element, 0);
            Set<String> matchingStrings = new LinkedHashSet<>();
            collectUsesAndStrings(units, trees, candidates, references, matchingStrings);
            List<Candidate> review = new ArrayList<>();
            List<Map<String, Object>> uncertain = new ArrayList<>();
            for (Candidate candidate : candidates.values()) {
                Candidate counted = candidate.withStaticReferences(references.getOrDefault(candidate.element(), 0));
                if (counted.staticReferences() != 0) continue;
                if (matchingStrings.contains(counted.name())) {
                    uncertain.add(mapOf(
                        "file", counted.file(), "line", counted.line(), "name", counted.name(), "kind", "private_method",
                        "reason", "An exact matching string literal may be reflective or dynamic reachability; static analysis cannot resolve it.",
                        "verdict", "uncertain"
                    ));
                } else {
                    review.add(counted);
                }
            }
            review.sort(Comparator.comparing(Candidate::file).thenComparingInt(Candidate::line).thenComparing(Candidate::name));
            uncertain.sort(Comparator.comparing(item -> String.valueOf(item.get("file"))));
            List<Map<String, Object>> flags = uncertaintyFlags(options.root(), scan);
            String status = scan.kotlin().isEmpty() ? "complete" : "partial";
            return successfulPayload(options, feature, sourceRoot, scan, selected, review, uncertain, flags, status);
        }
    }

    private static List<Path> selectedSources(Path root, Path target) throws IOException {
        List<Path> sources = new ArrayList<>();
        if (Files.isRegularFile(target, LinkOption.NOFOLLOW_LINKS)) {
            if (target.getFileName().toString().endsWith(".java") && !generated(target)) sources.add(target);
            return sources;
        }
        if (!Files.isDirectory(target, LinkOption.NOFOLLOW_LINKS)) return sources;
        Files.walkFileTree(target, Set.of(), Integer.MAX_VALUE, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) {
                return dir.equals(target) || !excluded(root, dir) ? FileVisitResult.CONTINUE : FileVisitResult.SKIP_SUBTREE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                if (file.getFileName().toString().endsWith(".java") && !excluded(root, file) && !generated(file)) {
                    sources.add(file.toAbsolutePath().normalize());
                }
                return FileVisitResult.CONTINUE;
            }
        });
        sources.sort(Comparator.comparing(path -> relative(root, path)));
        return sources;
    }

    private static Path inferSourceRoot(Path root, Path source) throws IOException, Terminal {
        Matcher matcher = PACKAGE.matcher(Files.readString(source, StandardCharsets.UTF_8));
        if (!matcher.find()) {
            throw new Terminal("unsupported", "default_package", "Java dormant v1 requires a named package.", 0, true);
        }
        String packageName = matcher.group(1);
        Path sourceRoot = source.getParent();
        for (String ignored : packageName.split("\\.")) sourceRoot = sourceRoot.getParent();
        if (sourceRoot == null || !sourceRoot.startsWith(root)) {
            throw new Terminal("unsupported", "source_root_unverifiable", "Could not infer a source root within project root.", 0, true);
        }
        Path expected = sourceRoot;
        for (String segment : packageName.split("\\.")) expected = expected.resolve(segment);
        if (!expected.equals(source.getParent())) {
            throw new Terminal(
                "unsupported", "package_path_mismatch",
                "Package declaration does not match the source path for " + relative(root, source) + ".", 0, true
            );
        }
        return sourceRoot;
    }

    private static SourceScan collectSources(Path root, Path sourceRoot) throws IOException {
        List<Path> eligible = new ArrayList<>();
        List<String> generated = new ArrayList<>();
        List<String> excluded = new ArrayList<>();
        List<String> kotlin = new ArrayList<>();
        List<String> symlinked = new ArrayList<>();
        Files.walkFileTree(sourceRoot, Set.of(), Integer.MAX_VALUE, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) {
                if (!dir.equals(sourceRoot) && (Files.isSymbolicLink(dir) || excluded(root, dir))) {
                    return FileVisitResult.SKIP_SUBTREE;
                }
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                String name = file.getFileName().toString();
                if (Files.isSymbolicLink(file)) {
                    if (name.endsWith(".java")) symlinked.add(relative(root, file));
                    return FileVisitResult.CONTINUE;
                }
                if (name.endsWith(".kt") || name.endsWith(".kts")) {
                    if (!excluded(root, file)) kotlin.add(relative(root, file));
                    return FileVisitResult.CONTINUE;
                }
                if (!name.endsWith(".java")) return FileVisitResult.CONTINUE;
                if (generated(file)) {
                    generated.add(relative(root, file));
                } else if (excluded(root, file)) {
                    excluded.add(relative(root, file));
                } else {
                    eligible.add(file.toAbsolutePath().normalize());
                }
                return FileVisitResult.CONTINUE;
            }
        });
        eligible.sort(Comparator.comparing(path -> relative(root, path)));
        generated.sort(String::compareTo);
        excluded.sort(String::compareTo);
        kotlin.sort(String::compareTo);
        symlinked.sort(String::compareTo);
        return new SourceScan(eligible, generated, excluded, kotlin, symlinked);
    }

    private static Map<URI, Path> pathsByUri(List<Path> sources) {
        Map<URI, Path> paths = new HashMap<>();
        for (Path source : sources) paths.put(source.toUri(), source);
        return paths;
    }

    private static Map<ExecutableElement, Candidate> collectCandidates(
        List<CompilationUnitTree> units,
        Map<URI, Path> paths,
        Set<Path> selected,
        Trees trees,
        Path root
    ) {
        Map<ExecutableElement, Candidate> candidates = new LinkedHashMap<>();
        for (CompilationUnitTree unit : units) {
            Path path = paths.get(unit.getSourceFile().toUri());
            if (!selected.contains(path)) continue;
            new TreePathScanner<Void, Void>() {
                @Override
                public Void visitMethod(MethodTree tree, Void unused) {
                    Element element = trees.getElement(getCurrentPath());
                    if (element instanceof ExecutableElement method
                        && method.getKind() == ElementKind.METHOD
                        && method.getModifiers().contains(Modifier.PRIVATE)) {
                        long start = trees.getSourcePositions().getStartPosition(unit, tree);
                        int line = start < 0 ? 0 : Math.toIntExact(unit.getLineMap().getLineNumber(start));
                        String owner = method.getEnclosingElement() instanceof TypeElement type
                            ? type.getQualifiedName().toString() : "";
                        String name = method.getSimpleName().toString();
                        String id = "java:" + relative(root, path) + ":" + line + ":" + name;
                        candidates.put(method, new Candidate(method, id, relative(root, path), line, name, owner, 0));
                    }
                    return super.visitMethod(tree, unused);
                }
            }.scan(unit, null);
        }
        return candidates;
    }

    private static void collectUsesAndStrings(
        List<CompilationUnitTree> units,
        Trees trees,
        Map<ExecutableElement, Candidate> candidates,
        Map<ExecutableElement, Integer> references,
        Set<String> matchingStrings
    ) {
        Set<String> candidateNames = new LinkedHashSet<>();
        for (Candidate candidate : candidates.values()) candidateNames.add(candidate.name());
        for (CompilationUnitTree unit : units) {
            new TreePathScanner<Void, Void>() {
                @Override
                public Void visitMethodInvocation(MethodInvocationTree tree, Void unused) {
                    count(trees.getElement(getCurrentPath()));
                    return super.visitMethodInvocation(tree, unused);
                }

                @Override
                public Void visitMemberReference(MemberReferenceTree tree, Void unused) {
                    count(trees.getElement(getCurrentPath()));
                    return super.visitMemberReference(tree, unused);
                }

                @Override
                public Void visitLiteral(LiteralTree tree, Void unused) {
                    if (tree.getValue() instanceof String value && candidateNames.contains(value)) matchingStrings.add(value);
                    return super.visitLiteral(tree, unused);
                }

                private void count(Element element) {
                    if (element instanceof ExecutableElement method && candidates.containsKey(method)) {
                        references.put(method, references.getOrDefault(method, 0) + 1);
                    }
                }
            }.scan(unit, null);
        }
    }

    private static List<Map<String, Object>> uncertaintyFlags(Path root, SourceScan scan) throws IOException {
        List<Map<String, Object>> flags = new ArrayList<>();
        if (!scan.generated().isEmpty()) {
            flags.add(mapOf(
                "kind", "generated_source_excluded",
                "message", "Generated Java source was excluded from compiler attribution and may register or reach symbols dynamically.",
                "evidence", scan.generated()
            ));
        }
        if (!scan.kotlin().isEmpty()) {
            flags.add(mapOf(
                "kind", "kotlin_source_unavailable",
                "message", "Kotlin source is outside Java/Javac v1 attribution; Java-only conclusions are incomplete.",
                "evidence", scan.kotlin()
            ));
        }
        List<String> dynamic = new ArrayList<>();
        for (Path source : scan.eligible()) {
            String text = Files.readString(source, StandardCharsets.UTF_8);
            if (text.contains("getDeclaredMethod") || text.contains("getMethod(") || text.contains("Class.forName")
                || text.contains("MethodHandles") || text.contains("ServiceLoader.load") || text.contains("Method.invoke")) {
                dynamic.add(relative(root, source));
            }
        }
        if (!dynamic.isEmpty()) {
            flags.add(mapOf(
                "kind", "reflection_or_dynamic_lookup",
                "message", "Reflection or dynamic lookup is present; zero compiler-resolved uses never prove runtime unreachability.",
                "evidence", dynamic
            ));
        }
        flags.add(mapOf(
            "kind", "runtime_boundary",
            "message", "Dependency injection, framework callbacks, JNI, external consumers, and runtime dispatch are outside this static review.",
            "evidence", List.of()
        ));
        return flags;
    }

    private static Map<String, Object> successfulPayload(
        Options options,
        int feature,
        Path sourceRoot,
        SourceScan scan,
        List<Path> selected,
        List<Candidate> candidates,
        List<Map<String, Object>> uncertain,
        List<Map<String, Object>> flags,
        String status
    ) {
        List<Map<String, Object>> rendered = new ArrayList<>();
        for (Candidate candidate : candidates) {
            List<String> uncertainty = new ArrayList<>();
            uncertainty.add("Static source resolution excludes reflection, dependency injection, framework callbacks, JNI, and external consumers.");
            if (!scan.generated().isEmpty()) uncertainty.add("Generated Java source was excluded from attribution.");
            if (!scan.kotlin().isEmpty()) uncertainty.add("Kotlin source is outside Java/Javac v1 attribution.");
            rendered.add(mapOf(
                "id", candidate.id(), "file", candidate.file(), "line", candidate.line(), "name", candidate.name(),
                "owner", candidate.owner(), "kind", "private_method", "static_references", candidate.staticReferences(),
                "verdict", "review_required", "recommendation", "human_review_only", "uncertainty", uncertainty
            ));
        }
        List<String> selectedFiles = selected.stream().map(path -> relative(options.root(), path)).sorted().toList();
        return mapOf(
            "schema_version", 1,
            "language", "java",
            "analyzer", "jdk17-javactask-trees",
            "status", status,
            "tooling", mapOf(
                "java_version", Runtime.version().toString(), "jdk_feature", feature,
                "minimum_jdk", options.minimumJdk(),
                "resolution", "JavacTask.parse+analyze --release 17 -proc:none --class-path ''"
            ),
            "target", mapOf(
                "path", relative(options.root(), options.target()),
                "kind", Files.isRegularFile(options.target(), LinkOption.NOFOLLOW_LINKS) ? "file" : "directory",
                "source_root", relative(options.root(), sourceRoot), "selected_source_files", selectedFiles
            ),
            "source_inventory", mapOf(
                "eligible", scan.eligible().size(), "generated", scan.generated().size(),
                "policy_excluded", scan.excluded().size(), "kotlin", scan.kotlin().size(),
                "generated_files", scan.generated(), "excluded_files", scan.excluded(), "kotlin_files", scan.kotlin()
            ),
            "project_resolution", mapOf(
                "state", status.equals("complete") ? "complete" : "partial",
                "model", "standalone_jdk17_source_root",
                "unavailable", status.equals("complete") ? List.of() : List.of("kotlin_source_not_attributed")
            ),
            "summary", mapOf(
                "review_required", rendered.size(), "uncertain", uncertain.size(), "certain_delete", 0
            ),
            "candidates", rendered,
            "uncertain_symbols", uncertain,
            "uncertainty_flags", flags
        );
    }

    private static Map<String, Object> terminalPayload(Options options, Terminal terminal) {
        return mapOf(
            "schema_version", 1,
            "language", "java",
            "analyzer", "jdk17-javactask-trees",
            "status", terminal.status(), "failure_kind", terminal.kind(), "message", terminal.message(),
            "target", mapOf("path", relative(options.root(), options.target())),
            "summary", mapOf("review_required", 0, "uncertain", 0, "certain_delete", 0),
            "candidates", List.of(), "uncertain_symbols", List.of(), "uncertainty_flags", List.of()
        );
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
            .orElse("Java compiler evidence is incomplete.");
    }

    private static boolean generated(Path path) throws IOException {
        String text = Files.readString(path, StandardCharsets.UTF_8);
        return text.lines().limit(5).anyMatch(line -> line.contains("Generated") && line.contains("DO NOT EDIT"))
            || GENERATED.matcher(text).find();
    }

    private static boolean excluded(Path root, Path path) {
        Path normalized = path.toAbsolutePath().normalize();
        if (!normalized.startsWith(root)) return true;
        for (Path part : root.relativize(normalized)) {
            if (EXCLUDED.contains(part.toString().toLowerCase(Locale.ROOT))) return true;
        }
        String name = normalized.getFileName().toString().toLowerCase(Locale.ROOT);
        return name.endsWith("test.java") || name.endsWith("tests.java") || name.endsWith("generated.java");
    }

    private static boolean traversesSymlink(Path root, Path candidate) {
        Path current = root;
        if (Files.isSymbolicLink(root)) return true;
        if (!candidate.startsWith(root)) return true;
        for (Path part : root.relativize(candidate)) {
            current = current.resolve(part);
            if (Files.exists(current, LinkOption.NOFOLLOW_LINKS) && Files.isSymbolicLink(current)) return true;
        }
        return false;
    }

    private static String relative(Path root, Path path) {
        Path normalized = path.toAbsolutePath().normalize();
        return normalized.startsWith(root) ? root.relativize(normalized).toString().replace('\\', '/') : normalized.toString();
    }

    private static void writeArtifacts(Options options, Map<String, Object> payload) throws IOException {
        writeAtomic(options.reportDir().resolve("findings.json"), json(payload) + "\n");
        writeAtomic(options.reportDir().resolve("report.md"), renderReport(payload));
        System.out.println("wrote " + relative(options.root(), options.reportDir().resolve("findings.json")) + " and "
            + relative(options.root(), options.reportDir().resolve("report.md")) + " (" + payload.get("status") + ")");
    }

    private static String renderReport(Map<String, Object> payload) {
        String status = String.valueOf(payload.get("status"));
        StringBuilder out = new StringBuilder();
        out.append("# Java dormant-code review\n\n")
            .append("> **Scope:** JDK 17 compiler-attributed Java source only; read-only.\n")
            .append("> **Safety:** Never safe deletion. Every candidate requires human runtime review.\n\n")
            .append("Status: **").append(status).append("**\n\n");
        if (!status.equals("complete") && !status.equals("partial")) {
            out.append("## Stop condition\n\n")
                .append(payload.getOrDefault("message", "Java compiler evidence was unavailable.")).append("\n");
            return out.toString();
        }
        if (status.equals("partial") && payload.containsKey("failure_kind")) {
            out.append("## Incomplete compiler evidence\n\n")
                .append(payload.get("message")).append("\n\n")
                .append("No Java semantic candidate fact is emitted until attribution succeeds.\n");
            return out.toString();
        }
        @SuppressWarnings("unchecked")
        Map<String, Object> summary = (Map<String, Object>) payload.get("summary");
        out.append("## Summary\n\n")
            .append("- Review-required candidates: ").append(summary.get("review_required")).append("\n")
            .append("- Uncertain symbols: ").append(summary.get("uncertain")).append("\n")
            .append("- Certain deletion findings: 0\n\n")
            .append("## Candidates\n\n| Symbol | Location | Compiler-resolved uses | Recommendation |\n")
            .append("|---|---|---:|---|\n");
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> candidates = (List<Map<String, Object>>) payload.get("candidates");
        for (Map<String, Object> candidate : candidates) {
            out.append("| `").append(candidate.get("name")).append("` | `")
                .append(candidate.get("file")).append(":").append(candidate.get("line"))
                .append("` | ").append(candidate.get("static_references"))
                .append(" | human review only |\n");
        }
        if (candidates.isEmpty()) out.append("| — | — | — | No static review candidate |\n");
        out.append("\n## Boundaries\n\n")
            .append("- reflection, dependency injection, framework callbacks, JNI, external consumers, and runtime dispatch are not proven by `javac`.\n")
            .append("- Kotlin, generated source, Maven/Gradle resolution, annotation processors, module paths, and runtime tests are outside this v1 model.\n")
            .append("- Resolve `partial` compiler evidence before treating the report as a clean Java source-root review.\n");
        return out.toString();
    }

    private static void writeAtomic(Path path, String contents) throws IOException {
        Files.createDirectories(path.getParent());
        Path temporary = path.resolveSibling(path.getFileName() + ".tmp-" + ProcessHandle.current().pid());
        Files.writeString(temporary, contents, StandardCharsets.UTF_8);
        try {
            Files.move(temporary, path, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (java.nio.file.AtomicMoveNotSupportedException ignored) {
            Files.move(temporary, path, StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private static Map<String, Object> mapOf(Object... values) {
        Map<String, Object> map = new LinkedHashMap<>();
        for (int index = 0; index < values.length; index += 2) map.put(String.valueOf(values[index]), values[index + 1]);
        return map;
    }

    private static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof String text) return "\"" + escape(text) + "\"";
        if (value instanceof Number || value instanceof Boolean) return String.valueOf(value);
        if (value instanceof Map<?, ?> map) {
            List<String> items = new ArrayList<>();
            for (Map.Entry<?, ?> entry : map.entrySet()) items.add(json(String.valueOf(entry.getKey())) + ":" + json(entry.getValue()));
            return "{" + String.join(",", items) + "}";
        }
        if (value instanceof Iterable<?> items) {
            List<String> rendered = new ArrayList<>();
            for (Object item : items) rendered.add(json(item));
            return "[" + String.join(",", rendered) + "]";
        }
        return json(String.valueOf(value));
    }

    private static String escape(String value) {
        StringBuilder out = new StringBuilder();
        for (int index = 0; index < value.length(); index++) {
            char character = value.charAt(index);
            switch (character) {
                case '\\' -> out.append("\\\\");
                case '\"' -> out.append("\\\"");
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
}

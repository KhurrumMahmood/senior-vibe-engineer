// Bounded Java package map using only JDK 17 JavacTask attribution.
// Run with: java map_java.java --name ... --target ... --project-root ... --output ... --evidence ...
// It is deliberately family-local: a copied skill needs only this source file and a JDK.
import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.ImportTree;
import com.sun.source.tree.MemberSelectTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.Tree;
import com.sun.source.tree.VariableTree;
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
import java.util.TreeMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.lang.model.element.Element;
import javax.lang.model.element.ElementKind;
import javax.lang.model.element.ExecutableElement;
import javax.lang.model.element.Modifier;
import javax.lang.model.element.NestingKind;
import javax.lang.model.element.TypeElement;
import javax.lang.model.element.VariableElement;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

class MapJava {
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

    private record Options(Path root, String name, Path target, Path output, Path evidence, int minimumJdk) {}
    private record SourceScan(
        List<Path> eligible, List<String> generated, List<String> excluded, List<String> kotlin,
        List<String> symlinked
    ) {}
    private record Symbol(String name, String qualifiedName, String owner, String kind, String file, int line) {}
    private record Edge(
        String fromPackage, String file, int line, String targetPackage, String referencedType,
        String style, String resolution
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
            writeArtifacts(options, run(options));
        } catch (Terminal terminal) {
            System.err.println("[map_java] " + terminal.kind() + ": " + terminal.message());
            if (terminal.write() && options != null) {
                try {
                    writeArtifacts(options, terminalPayload(options, terminal));
                } catch (IOException writeError) {
                    System.err.println("[map_java] " + writeError.getMessage());
                    System.exit(2);
                    return;
                }
            }
            if (terminal.exit() != 0) System.exit(terminal.exit());
        } catch (IllegalArgumentException error) {
            System.err.println(error.getMessage());
            System.exit(2);
        } catch (Exception error) {
            System.err.println("[map_java] " + error.getMessage());
            System.exit(2);
        }
    }

    private static Options parseArgs(String[] args) {
        if (args.length % 2 != 0) throw usage();
        Map<String, String> values = new HashMap<>();
        Set<String> allowed = Set.of("--name", "--target", "--project-root", "--output", "--evidence", "--minimum-jdk");
        for (int index = 0; index < args.length; index += 2) {
            if (!allowed.contains(args[index]) || values.put(args[index], args[index + 1]) != null) throw usage();
        }
        for (String required : List.of("--name", "--target", "--project-root", "--output", "--evidence")) {
            if (!values.containsKey(required)) throw usage();
        }
        String name = values.get("--name");
        if (!name.matches("[a-z0-9][a-z0-9-]*")) {
            throw new IllegalArgumentException("--name must be lowercase kebab-case");
        }
        Path root = Path.of(values.get("--project-root")).toAbsolutePath().normalize();
        return new Options(
            root,
            name,
            resolveInside(root, values.get("--target"), "target"),
            resolveInside(root, values.get("--output"), "output"),
            resolveInside(root, values.get("--evidence"), "evidence"),
            positiveInt(values.getOrDefault("--minimum-jdk", "17"), "--minimum-jdk")
        );
    }

    private static IllegalArgumentException usage() {
        return new IllegalArgumentException(
            "usage: map_java.java --name <kebab-name> --target <package-directory> --project-root <root> "
                + "--output .claude/docs/subsystems/<name>.md --evidence reports/map/<name>/java-map.json [--minimum-jdk 17]"
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
        Path docs = options.root().resolve(".claude/docs/subsystems");
        Path reports = options.root().resolve("reports/map");
        if (!options.output().startsWith(docs) || options.output().equals(docs)) {
            throw new IllegalArgumentException("output must stay below .claude/docs/subsystems");
        }
        if (!options.evidence().startsWith(reports) || options.evidence().equals(reports)) {
            throw new IllegalArgumentException("evidence must stay below reports/map");
        }
        if (Files.isSymbolicLink(options.root()) || traversesSymlink(options.root(), options.output())
            || traversesSymlink(options.root(), options.evidence())) {
            throw new IllegalArgumentException("artifact output must not traverse a symbolic link");
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
        if (!Files.isDirectory(options.target(), LinkOption.NOFOLLOW_LINKS)) {
            throw new Terminal("unsupported", "target_not_directory", "Java map v1 requires one package directory.", 0, true);
        }
        if (excluded(options.root(), options.target())) {
            throw new Terminal(
                "unsupported", "excluded_target",
                "Generated, vendor, test, and build targets are outside Java map v1.", 0, true
            );
        }
        List<Path> targetSources = directTargetSources(options.root(), options.target());
        if (targetSources.isEmpty()) {
            throw new Terminal("unsupported", "no_eligible_java_source", "Target contains no eligible Java source.", 0, true);
        }
        Path sourceRoot = inferSourceRoot(options.root(), targetSources.get(0));
        SourceScan scan = collectSources(options.root(), sourceRoot);
        if (!scan.symlinked().isEmpty()) {
            throw new Terminal(
                "unsupported", "unsafe_source",
                "Java source root contains a symbolic-link source: " + scan.symlinked().get(0), 0, true
            );
        }
        if (!scan.eligible().containsAll(targetSources)) {
            throw new Terminal(
                "unsupported", "selected_source_unavailable",
                "Every selected package source must be eligible, non-generated production Java.", 0, true
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
                throw new Terminal("failed", "syntax_error", firstDiagnostic(options.root(), diagnostics), 2, true);
            }
            task.analyze();
            if (hasErrors(diagnostics)) {
                throw new Terminal(
                    "partial", "unresolved_compilation", firstDiagnostic(options.root(), diagnostics), 0, true
                );
            }
            Trees trees = Trees.instance(task);
            Map<URI, Path> paths = pathsByUri(scan.eligible());
            Set<Path> targetSet = new LinkedHashSet<>(targetSources);
            String targetPackage = packageForTarget(units, paths, targetSet);
            Map<String, TypeElement> firstPartyTypes = firstPartyTypes(units, trees);
            List<Symbol> exported = exportedSurface(units, paths, targetSet, trees, options.root());
            EdgeSets edges = edges(units, paths, targetSet, targetPackage, firstPartyTypes, trees, options.root());
            String status = scan.kotlin().isEmpty() ? "complete" : "partial";
            return successfulPayload(
                options, feature, sourceRoot, scan, targetSources, targetPackage, exported, edges, status
            );
        }
    }

    private static List<Path> directTargetSources(Path root, Path target) throws IOException, Terminal {
        List<Path> sources = new ArrayList<>();
        try (var stream = Files.list(target)) {
            for (Path path : stream.sorted().toList()) {
                String name = path.getFileName().toString();
                if (!name.endsWith(".java")) continue;
                if (Files.isSymbolicLink(path)) {
                    throw new Terminal("unsupported", "unsafe_source", "Target Java source must not be a symbolic link.", 0, true);
                }
                if (Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS) && !generated(path) && !excluded(root, path)) {
                    sources.add(path.toAbsolutePath().normalize());
                }
            }
        }
        sources.sort(Comparator.comparing(path -> relative(root, path)));
        return sources;
    }

    private static Path inferSourceRoot(Path root, Path source) throws IOException, Terminal {
        Matcher matcher = PACKAGE.matcher(Files.readString(source, StandardCharsets.UTF_8));
        if (!matcher.find()) {
            throw new Terminal("unsupported", "default_package", "Java map v1 requires a named package.", 0, true);
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

    private static String packageForTarget(
        List<CompilationUnitTree> units, Map<URI, Path> paths, Set<Path> targetSources
    ) throws Terminal {
        Set<String> packages = new LinkedHashSet<>();
        for (CompilationUnitTree unit : units) {
            if (targetSources.contains(paths.get(unit.getSourceFile().toUri()))) {
                packages.add(unit.getPackageName() == null ? "" : unit.getPackageName().toString());
            }
        }
        if (packages.size() != 1 || packages.contains("")) {
            throw new Terminal(
                "unsupported", "mixed_or_default_package",
                "Target must contain one named Java package.", 0, true
            );
        }
        return packages.iterator().next();
    }

    private static Map<String, TypeElement> firstPartyTypes(List<CompilationUnitTree> units, Trees trees) {
        Map<String, TypeElement> types = new LinkedHashMap<>();
        for (CompilationUnitTree unit : units) {
            new TreePathScanner<Void, Void>() {
                @Override
                public Void visitClass(ClassTree tree, Void unused) {
                    Element element = trees.getElement(getCurrentPath());
                    if (element instanceof TypeElement type && !type.getQualifiedName().toString().isEmpty()) {
                        types.put(type.getQualifiedName().toString(), type);
                    }
                    return super.visitClass(tree, unused);
                }
            }.scan(unit, null);
        }
        return types;
    }

    private static List<Symbol> exportedSurface(
        List<CompilationUnitTree> units,
        Map<URI, Path> paths,
        Set<Path> targetSources,
        Trees trees,
        Path root
    ) {
        List<Symbol> symbols = new ArrayList<>();
        for (CompilationUnitTree unit : units) {
            Path path = paths.get(unit.getSourceFile().toUri());
            if (!targetSources.contains(path)) continue;
            new TreePathScanner<Void, Void>() {
                @Override
                public Void visitClass(ClassTree tree, Void unused) {
                    Element element = trees.getElement(getCurrentPath());
                    if (element instanceof TypeElement type && type.getModifiers().contains(Modifier.PUBLIC)
                        && publiclyAccessible(type)) {
                        add(tree, type, "type", type.getQualifiedName().toString(), "");
                    }
                    return super.visitClass(tree, unused);
                }

                @Override
                public Void visitMethod(MethodTree tree, Void unused) {
                    Element element = trees.getElement(getCurrentPath());
                    if (element instanceof ExecutableElement method && method.getModifiers().contains(Modifier.PUBLIC)
                        && publiclyAccessible(method)) {
                        String kind = method.getKind() == ElementKind.CONSTRUCTOR ? "constructor" : "method";
                        String owner = owner(method);
                        add(tree, method, kind, owner + "#" + method.getSimpleName(), owner);
                    }
                    return super.visitMethod(tree, unused);
                }

                @Override
                public Void visitVariable(VariableTree tree, Void unused) {
                    Element element = trees.getElement(getCurrentPath());
                    if (element instanceof VariableElement variable && variable.getModifiers().contains(Modifier.PUBLIC)
                        && variable.getKind() == ElementKind.FIELD && publiclyAccessible(variable)) {
                        String owner = owner(variable);
                        add(tree, variable, "field", owner + "#" + variable.getSimpleName(), owner);
                    }
                    return super.visitVariable(tree, unused);
                }

                private void add(Tree tree, Element element, String kind, String qualified, String owner) {
                    long start = trees.getSourcePositions().getStartPosition(unit, tree);
                    int line = start < 0 ? 0 : Math.toIntExact(unit.getLineMap().getLineNumber(start));
                    symbols.add(new Symbol(
                        element.getSimpleName().toString(), qualified, owner, kind, relative(root, path), line
                    ));
                }
            }.scan(unit, null);
        }
        symbols.sort(Comparator.comparing(Symbol::file).thenComparingInt(Symbol::line).thenComparing(Symbol::qualifiedName));
        return symbols;
    }

    private static boolean publiclyAccessible(Element element) {
        Element current = element;
        while (current != null) {
            if (current instanceof TypeElement type) {
                if (type.getNestingKind() != NestingKind.TOP_LEVEL && !type.getModifiers().contains(Modifier.PUBLIC)) return false;
                if (type.getNestingKind() == NestingKind.TOP_LEVEL && !type.getModifiers().contains(Modifier.PUBLIC)) return false;
            }
            current = current.getEnclosingElement();
        }
        return true;
    }

    private static String owner(Element element) {
        Element current = element.getEnclosingElement();
        while (current != null) {
            if (current instanceof TypeElement type) return type.getQualifiedName().toString();
            current = current.getEnclosingElement();
        }
        return "";
    }

    private record EdgeSets(List<Edge> outbound, List<Edge> inbound, List<Edge> external) {}

    private static EdgeSets edges(
        List<CompilationUnitTree> units,
        Map<URI, Path> paths,
        Set<Path> targetSources,
        String targetPackage,
        Map<String, TypeElement> firstPartyTypes,
        Trees trees,
        Path root
    ) {
        Map<String, Edge> outbound = new TreeMap<>();
        Map<String, Edge> inbound = new TreeMap<>();
        Map<String, Edge> external = new TreeMap<>();
        for (CompilationUnitTree unit : units) {
            Path path = paths.get(unit.getSourceFile().toUri());
            boolean sourceIsTarget = targetSources.contains(path);
            String sourcePackage = unit.getPackageName() == null ? "" : unit.getPackageName().toString();
            new TreePathScanner<Void, Void>() {
                @Override
                public Void visitImport(ImportTree tree, Void unused) {
                    Element element = trees.getElement(new TreePath(getCurrentPath(), tree.getQualifiedIdentifier()));
                    handle(tree, element, tree.isStatic() ? "static_import" : "import", tree.getQualifiedIdentifier().toString());
                    return null;
                }

                @Override
                public Void visitMemberSelect(MemberSelectTree tree, Void unused) {
                    Element element = trees.getElement(getCurrentPath());
                    handle(tree, element, "fully_qualified", tree.toString());
                    return super.visitMemberSelect(tree, unused);
                }

                private void handle(Tree tree, Element element, String style, String text) {
                    TypeElement type = typeElement(element);
                    if (type == null) return;
                    String qualified = type.getQualifiedName().toString();
                    if (qualified.isEmpty()) return;
                    boolean firstParty = firstPartyTypes.containsKey(qualified);
                    if (style.equals("fully_qualified") && !text.equals(qualified)) return;
                    long start = trees.getSourcePositions().getStartPosition(unit, tree);
                    int line = start < 0 ? 0 : Math.toIntExact(unit.getLineMap().getLineNumber(start));
                    String target = type.getEnclosingElement().toString();
                    Edge edge = new Edge(sourcePackage, relative(root, path), line, target, qualified, style,
                        firstParty ? "compiler_resolved_first_party" : "compiler_resolved_external");
                    if (firstParty && sourceIsTarget && !target.equals(targetPackage)) add(outbound, edge);
                    else if (firstParty && !sourceIsTarget && target.equals(targetPackage) && !sourcePackage.equals(targetPackage)) add(inbound, edge);
                    else if (!firstParty && sourceIsTarget) add(external, edge);
                }
            }.scan(unit, null);
        }
        return new EdgeSets(new ArrayList<>(outbound.values()), new ArrayList<>(inbound.values()), new ArrayList<>(external.values()));
    }

    private static TypeElement typeElement(Element element) {
        Element current = element;
        while (current != null) {
            if (current instanceof TypeElement type) return type;
            current = current.getEnclosingElement();
        }
        return null;
    }

    private static void add(Map<String, Edge> edges, Edge edge) {
        String key = edge.file() + ":" + edge.line() + ":" + edge.style() + ":" + edge.referencedType();
        edges.put(key, edge);
    }

    private static Map<String, Object> successfulPayload(
        Options options,
        int feature,
        Path sourceRoot,
        SourceScan scan,
        List<Path> targetSources,
        String targetPackage,
        List<Symbol> exported,
        EdgeSets edges,
        String status
    ) {
        List<String> targetFiles = targetSources.stream().map(path -> relative(options.root(), path)).sorted().toList();
        List<String> targetExcluded = scan.generated().stream()
            .filter(path -> Path.of(path).getParent().toString().replace('\\', '/').equals(relative(options.root(), options.target())))
            .toList();
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
                "path", relative(options.root(), options.target()), "kind", "package_directory", "package", targetPackage,
                "source_root", relative(options.root(), sourceRoot), "source_files", targetFiles.size(),
                "eligible_files", targetFiles, "excluded_files", targetExcluded
            ),
            "source_inventory", mapOf(
                "eligible", scan.eligible().size(), "generated", scan.generated().size(),
                "policy_excluded", scan.excluded().size(), "kotlin", scan.kotlin().size(),
                "generated_files", scan.generated(), "excluded_files", scan.excluded(), "kotlin_files", scan.kotlin()
            ),
            "counts", mapOf(
                "source_files", targetFiles.size(), "public_symbols", exported.size(),
                "outbound_imports", edges.outbound().size(), "inbound_imports", edges.inbound().size(),
                "external_imports", edges.external().size()
            ),
            "exported_surface", exported.stream().map(MapJava::symbolMap).toList(),
            "outbound_imports", edges.outbound().stream().map(MapJava::edgeMap).toList(),
            "inbound_imports", edges.inbound().stream().map(MapJava::edgeMap).toList(),
            "external_imports", edges.external().stream().map(MapJava::edgeMap).toList(),
            "completeness", mapOf(
                "compiler_attribution", "complete",
                "first_party_type_edges", status.equals("complete") ? "complete" : "partial",
                "kotlin_sources", scan.kotlin().isEmpty() ? "none_detected" : "unavailable",
                "build_system", "unavailable_no_maven_or_gradle_model",
                "annotation_processing", "disabled_proc_none",
                "module_path", "unavailable"
            ),
            "unavailable", List.of(
                "Maven/Gradle/classpath/module-path resolution", "annotation processors", "runtime dispatch",
                "Kotlin attribution", "build-variant matrix", "responsibility judgment"
            )
        );
    }

    private static Map<String, Object> symbolMap(Symbol symbol) {
        return mapOf(
            "name", symbol.name(), "qualified_name", symbol.qualifiedName(), "owner", symbol.owner(),
            "kind", symbol.kind(), "file", symbol.file(), "line", symbol.line(), "visibility", "public"
        );
    }

    private static Map<String, Object> edgeMap(Edge edge) {
        return mapOf(
            "from_package", edge.fromPackage(), "file", edge.file(), "line", edge.line(),
            "target_package", edge.targetPackage(), "referenced_type", edge.referencedType(),
            "style", edge.style(), "resolution", edge.resolution()
        );
    }

    private static Map<String, Object> terminalPayload(Options options, Terminal terminal) {
        return mapOf(
            "schema_version", 1,
            "language", "java",
            "analyzer", "jdk17-javactask-trees",
            "status", terminal.status(), "failure_kind", terminal.kind(), "message", terminal.message(),
            "target", mapOf("path", relative(options.root(), options.target()), "kind", "package_directory"),
            "counts", mapOf("source_files", 0, "public_symbols", 0, "outbound_imports", 0, "inbound_imports", 0),
            "exported_surface", List.of(), "outbound_imports", List.of(), "inbound_imports", List.of(),
            "external_imports", List.of(),
            "completeness", mapOf("compiler_attribution", "unavailable")
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
        writeAtomic(options.evidence(), json(payload) + "\n");
        writeAtomic(options.output(), renderMap(payload));
        System.out.println("wrote " + relative(options.root(), options.evidence()) + " and "
            + relative(options.root(), options.output()) + " (" + payload.get("status") + ")");
    }

    private static String renderMap(Map<String, Object> payload) {
        String status = String.valueOf(payload.get("status"));
        @SuppressWarnings("unchecked")
        Map<String, Object> target = (Map<String, Object>) payload.get("target");
        StringBuilder out = new StringBuilder();
        out.append("---\n")
            .append("subsystem: ").append(target.get("path")).append("\n")
            .append("language: java\n")
            .append("status: ").append(status).append("\n")
            .append("---\n\n")
            .append("# Java subsystem map — `").append(target.get("path")).append("`\n\n")
            .append("> JDK 17 `JavacTask.parse()` + `analyze()` facts only; source is read-only.\n\n")
            .append("Status: **").append(status).append("**\n\n");
        if (!status.equals("complete") && !status.equals("partial")) {
            out.append("## Stop condition\n\n").append(payload.getOrDefault("message", "Java map evidence unavailable.")).append("\n");
            return out.toString();
        }
        if (status.equals("partial") && payload.containsKey("failure_kind")) {
            out.append("## Incomplete compiler evidence\n\n")
                .append(payload.get("message")).append("\n\n")
                .append("No public-surface or dependency-edge fact is emitted until attribution succeeds.\n");
            return out.toString();
        }
        @SuppressWarnings("unchecked")
        Map<String, Object> counts = (Map<String, Object>) payload.get("counts");
        out.append("## Inventory\n\n")
            .append("- Package: `").append(target.get("package")).append("`\n")
            .append("- Inferred source root: `").append(target.get("source_root")).append("`\n")
            .append("- Eligible target source files: ").append(counts.get("source_files")).append("\n")
            .append("- Public symbols: ").append(counts.get("public_symbols")).append("\n\n")
            .append("## Public surface\n\n| Symbol | Kind | Location |\n|---|---|---|\n");
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> symbols = (List<Map<String, Object>>) payload.get("exported_surface");
        for (Map<String, Object> symbol : symbols) {
            out.append("| `").append(symbol.get("qualified_name")).append("` | ")
                .append(symbol.get("kind")).append(" | `").append(symbol.get("file")).append(":")
                .append(symbol.get("line")).append("` |\n");
        }
        if (symbols.isEmpty()) out.append("| — | — | No public Java declaration attributed |\n");
        out.append("\n## Compiler-resolved first-party edges\n\n");
        renderEdges(out, "Outbound", payload.get("outbound_imports"));
        renderEdges(out, "Inbound", payload.get("inbound_imports"));
        out.append("## Boundaries\n\n")
            .append("- Maven/Gradle, external classpaths, module paths, annotation processors, Kotlin, runtime dispatch, and build variants are outside this v1 model.\n")
            .append("- A `partial` map is not a clean whole-project dependency graph; resolve the unavailable boundary before relying on it for structural work.\n");
        return out.toString();
    }

    private static void renderEdges(StringBuilder out, String heading, Object raw) {
        out.append("### ").append(heading).append("\n\n| File | Type | Style | Evidence |\n|---|---|---|---|\n");
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> edges = (List<Map<String, Object>>) raw;
        for (Map<String, Object> edge : edges) {
            out.append("| `").append(edge.get("file")).append(":").append(edge.get("line"))
                .append("` | `").append(edge.get("referenced_type")).append("` | ")
                .append(edge.get("style")).append(" | ").append(edge.get("resolution")).append(" |\n");
        }
        if (edges.isEmpty()) out.append("| — | — | — | No compiler-resolved first-party edge |\n");
        out.append("\n");
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

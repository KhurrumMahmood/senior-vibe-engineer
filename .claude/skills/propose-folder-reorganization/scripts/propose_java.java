// Produce one conservative Java 17 subpackage move plan from compiler facts.
// The command is read-only except for its two report artifacts and uses only
// source-file mode plus the JDK compiler tree/type APIs.
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.ImportTree;
import com.sun.source.tree.MemberSelectTree;
import com.sun.source.tree.Tree;
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
import java.util.regex.Pattern;
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
    private static final Set<String> PRUNE = Set.of(
        ".agents", ".claude", ".git", ".gradle", ".idea", ".venv",
        "node_modules", "reports", "venv"
    );
    private static final Set<String> GENERATED = Set.of("generated", "gen");
    private static final Set<String> TEST = Set.of(
        "test", "tests", "testfixtures", "fixtures", "fixture", "integrationtest"
    );
    private static final Set<String> VENDOR = Set.of("vendor");
    private static final Set<String> BUILD = Set.of("build", "target", "out", "dist");
    private static final Pattern GENERATED_ANNOTATION = Pattern.compile(
        "(?m)^\\s*@(javax\\.annotation\\.processing\\.)?Generated(?:\\s*\\(|\\s*$)"
    );

    private record Options(
        Path root,
        Path parent,
        String prefix,
        String clusterJudgment,
        String conventionJudgment,
        int minimumJdk,
        Path inspection,
        Path proposal
    ) {}

    private record Move(String current, String proposed, List<String> publicTypes) {}

    private record Impact(
        String file,
        int line,
        String kind,
        String current,
        String proposed,
        String resolution,
        String note
    ) {}

    private record Blocker(String kind, String file, int line, String reason) {}

    private record Parsed(
        List<CompilationUnitTree> units,
        Trees trees,
        Map<URI, Path> paths,
        DiagnosticCollector<JavaFileObject> diagnostics,
        StandardJavaFileManager manager
    ) implements AutoCloseable {
        @Override
        public void close() throws IOException {
            manager.close();
        }
    }

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
                writeArtifacts(options, outcome.payload);
            } catch (IOException error) {
                System.err.println(error.getMessage());
                System.exit(2);
                return;
            }
        } catch (Exception error) {
            exit = 2;
            Map<String, Object> payload = terminalPayload(
                options,
                "failed",
                "defer_internal_error",
                "internal_error",
                message(error)
            );
            try {
                writeArtifacts(options, payload);
            } catch (IOException ignored) {
                // Keep the original failure as the primary diagnostic.
            }
        }
        if (exit != 0) System.exit(exit);
    }

    private static Options parseArgs(String[] args) {
        Map<String, String> values = new HashMap<>();
        Set<String> allowed = Set.of(
            "--parent", "--prefix", "--cluster-judgment", "--convention-judgment",
            "--project-root", "--minimum-jdk", "--inspection", "--proposal"
        );
        if (args.length % 2 != 0) throw usage();
        for (int index = 0; index < args.length; index += 2) {
            if (!allowed.contains(args[index]) || values.put(args[index], args[index + 1]) != null) {
                throw usage();
            }
        }
        for (String required : List.of(
            "--parent", "--prefix", "--cluster-judgment", "--convention-judgment",
            "--project-root", "--inspection", "--proposal"
        )) {
            if (!values.containsKey(required)) throw usage();
        }
        String cluster = values.get("--cluster-judgment");
        String convention = values.get("--convention-judgment");
        if (!Set.of("split", "cohesive").contains(cluster)
            || !Set.of("approve-subpackage", "deny-subpackage").contains(convention)) {
            throw usage();
        }
        String prefix = values.get("--prefix");
        if (prefix.isBlank() || !Character.isJavaIdentifierStart(prefix.charAt(0))
            || prefix.chars().skip(1).anyMatch(value -> !Character.isJavaIdentifierPart(value))) {
            throw new IllegalArgumentException("--prefix must be one Java package identifier");
        }
        Path root = Path.of(values.get("--project-root")).toAbsolutePath().normalize();
        Path parent = inside(root, values.get("--parent"), "parent");
        Path inspection = inside(root, values.get("--inspection"), "inspection");
        Path proposal = inside(root, values.get("--proposal"), "proposal");
        Path reportRoot = root.resolve("reports/propose-folder-reorganization");
        if (!inspection.startsWith(reportRoot) || inspection.equals(reportRoot)
            || !proposal.startsWith(reportRoot) || proposal.equals(reportRoot)) {
            throw new IllegalArgumentException(
                "artifacts must stay below reports/propose-folder-reorganization"
            );
        }
        int minimumJdk = positiveInt(values.getOrDefault("--minimum-jdk", "17"));
        if (minimumJdk < 17) throw new IllegalArgumentException("minimum JDK must be at least 17");
        return new Options(
            root, parent, prefix, cluster, convention, minimumJdk, inspection, proposal
        );
    }

    private static IllegalArgumentException usage() {
        return new IllegalArgumentException(
            "usage: propose_java.java --parent PACKAGE_DIR --prefix PREFIX "
                + "--cluster-judgment split|cohesive "
                + "--convention-judgment approve-subpackage|deny-subpackage "
                + "--project-root ROOT --inspection FILE --proposal FILE"
        );
    }

    private static Path inside(Path root, String supplied, String label) {
        Path value = Path.of(supplied);
        if (!value.isAbsolute()) value = root.resolve(value);
        value = value.toAbsolutePath().normalize();
        if (!value.startsWith(root)) {
            throw new IllegalArgumentException(label + " must stay inside project root");
        }
        return value;
    }

    private static int positiveInt(String value) {
        try {
            int parsed = Integer.parseInt(value);
            if (parsed > 0) return parsed;
        } catch (NumberFormatException ignored) {
            // Fall through to one stable CLI error.
        }
        throw new IllegalArgumentException("--minimum-jdk must be a positive integer");
    }

    private static void run(Options options) throws Exception {
        if (Runtime.version().feature() < options.minimumJdk) {
            throw new Outcome(terminalPayload(
                options,
                "unsupported",
                "defer_jdk_version",
                "jdk_version_too_old",
                "JDK " + Runtime.version().feature() + " is below required JDK " + options.minimumJdk
            ), 0);
        }
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) {
            throw new Outcome(terminalPayload(
                options, "unsupported", "defer_tool_missing", "javac_tool_missing",
                "A full JDK with javac is required."
            ), 0);
        }
        if (!Files.isDirectory(options.root, LinkOption.NOFOLLOW_LINKS)
            || Files.isSymbolicLink(options.root)) {
            throw new Outcome(terminalPayload(
                options, "unsupported", "defer_project_root", "project_root_missing",
                "Project root must be a non-symlink directory."
            ), 0);
        }
        if (traversesSymlink(options.root, options.parent)
            || !Files.isDirectory(options.parent, LinkOption.NOFOLLOW_LINKS)) {
            throw new Outcome(terminalPayload(
                options, "unsupported", "defer_target_not_found", "unsafe_or_missing_parent",
                "Parent must be one root-contained, non-symlink Java package directory."
            ), 0);
        }

        List<Path> cluster = directClusterSources(options.parent, options.prefix);
        if (cluster.size() < 3) {
            throw new Outcome(terminalPayload(
                options, "deferred", "defer_below_threshold", "cluster_below_threshold",
                "Fewer than three direct Java source siblings match the requested prefix."
            ), 0);
        }
        if (options.clusterJudgment.equals("cohesive")) {
            throw new Outcome(terminalPayload(
                options, "deferred", "defer_cohesive_cluster", "cohesive_cluster",
                "The human judged this cluster deliberately cohesive. No move plan was emitted."
            ), 0);
        }
        if (options.conventionJudgment.equals("deny-subpackage")) {
            throw new Outcome(terminalPayload(
                options, "deferred", "defer_project_convention", "project_convention_denied",
                "The human judged a Java subpackage inconsistent with this project's conventions. No move plan was emitted."
            ), 0);
        }

        String oldPackage = parsePackage(compiler, options.root, cluster);
        Path sourceRoot = sourceRoot(options.parent, oldPackage);
        String newPackage = oldPackage + "." + options.prefix;
        Path destination = options.parent.resolve(options.prefix);
        List<Blocker> blockers = new ArrayList<>();
        if (Files.exists(destination, LinkOption.NOFOLLOW_LINKS)) {
            blockers.add(new Blocker(
                "destination_exists", relative(options.root, destination), 0,
                "The proposed subpackage path already exists."
            ));
        }
        for (Path selected : cluster) {
            if (generated(selected)) {
                blockers.add(new Blocker(
                    "generated_cluster_source", relative(options.root, selected), 0,
                    "Generated Java source cannot establish a human-owned cluster move."
                ));
            }
        }

        List<Path> sources = collectCurrentSourceRoot(options.root, sourceRoot, blockers);
        if (sources.isEmpty()) {
            throw new Outcome(terminalPayload(
                options, "unsupported", "defer_no_source", "no_current_source_root",
                "The current Java source root contains no eligible source."
            ), 0);
        }
        Set<String> selectedNames = new LinkedHashSet<>();
        for (Path path : cluster) {
            selectedNames.add(path.getFileName().toString().replaceFirst("\\.java$", ""));
        }
        blockers.addAll(excludedAmbiguities(options.root, sourceRoot, oldPackage, selectedNames));

        try (Parsed parsed = parseAndAnalyze(compiler, options.root, sources)) {
            Map<Path, CompilationUnitTree> unitByPath = new HashMap<>();
            for (CompilationUnitTree unit : parsed.units) {
                unitByPath.put(parsed.paths.get(unit.getSourceFile().toUri()), unit);
            }
            validatePackageTopology(
                options.root, sourceRoot, oldPackage, sources, parsed.units, parsed.paths, blockers
            );
            Set<Path> selectedPaths = Set.copyOf(cluster);
            Set<String> selectedQualified = new LinkedHashSet<>();
            Map<String, Path> declarationFiles = new HashMap<>();
            List<Move> moves = new ArrayList<>();
            for (Path selected : cluster) {
                CompilationUnitTree unit = unitByPath.get(selected);
                List<String> publicTypes = publicTopLevelTypes(unit, parsed.trees);
                String expected = selected.getFileName().toString().replaceFirst("\\.java$", "");
                if (!publicTypes.contains(expected)) {
                    blockers.add(new Blocker(
                        "cluster_file_public_type_mismatch", relative(options.root, selected), 0,
                        "Each selected file must own a same-named public top-level type."
                    ));
                }
                for (String type : publicTypes) {
                    selectedQualified.add(oldPackage + "." + type);
                    declarationFiles.put(oldPackage + "." + type, selected);
                }
                moves.add(new Move(
                    relative(options.root, selected),
                    relative(options.root, destination.resolve(selected.getFileName())),
                    publicTypes
                ));
            }
            List<Impact> impacts = impacts(
                options.root,
                parsed.units,
                parsed.paths,
                parsed.trees,
                selectedPaths,
                selectedQualified,
                oldPackage,
                newPackage,
                blockers
            );
            String status = blockers.isEmpty() ? "ready" : "blocked";
            String recommendation = blockers.isEmpty() ? "refactor" : "defer_blocked";
            Map<String, Object> payload = mapOf(
                "schema_version", 1,
                "skill", "propose-folder-reorganization",
                "language", "java",
                "status", status,
                "recommendation", recommendation,
                "read_only", true,
                "analyzer", "jdk-compiler-tree-type-api",
                "tooling", mapOf(
                    "java_version", Runtime.version().toString(),
                    "minimum_jdk", options.minimumJdk,
                    "compiler_mode", "JavacTask.parse+analyze --release 17 -proc:none",
                    "external_tools", List.of()
                ),
                "judgment", judgment(options),
                "parent", relative(options.root, options.parent),
                "prefix", options.prefix,
                "source_root", relative(options.root, sourceRoot),
                "old_package", oldPackage,
                "new_package", newPackage,
                "moves", moves.stream().map(ProposeJava::moveMap).toList(),
                "impacts", impacts.stream().map(ProposeJava::impactMap).toList(),
                "blockers", blockers.stream().map(ProposeJava::blockerMap).toList(),
                "native_obligations", mapOf(
                    "compile", "javac --release 17 -proc:none -d <classes> <current-source-root .java files>",
                    "tests", "Run the project's existing native test command before and after the separately approved move.",
                    "framework_inference", "none"
                ),
                "limitations", List.of(
                    "Only the current Java source root is compiled and attributed.",
                    "No framework, build-system, annotation-processor, reflection, generated-source, or external-consumer convention is inferred."
                )
            );
            writeArtifacts(options, payload);
        } catch (CompilerFailure failure) {
            Map<String, Object> payload = terminalPayload(
                options,
                failure.syntax ? "failed" : "blocked",
                failure.syntax ? "defer_syntax_error" : "defer_unresolved_compilation",
                failure.syntax ? "syntax_error" : "unresolved_compilation",
                failure.getMessage()
            );
            throw new Outcome(payload, failure.syntax ? 2 : 0);
        }
    }

    private static List<Path> directClusterSources(Path parent, String prefix) throws IOException {
        String lower = prefix.toLowerCase(Locale.ROOT);
        try (var stream = Files.list(parent)) {
            return stream
                .filter(path -> Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS))
                .filter(path -> path.getFileName().toString().endsWith(".java"))
                .filter(path -> {
                    String stem = path.getFileName().toString().replaceFirst("\\.java$", "");
                    if (!stem.toLowerCase(Locale.ROOT).startsWith(lower) || stem.length() <= prefix.length()) {
                        return false;
                    }
                    char boundary = stem.charAt(prefix.length());
                    return Character.isUpperCase(boundary) || boundary == '_';
                })
                .sorted()
                .toList();
        }
    }

    private static String parsePackage(JavaCompiler compiler, Path root, List<Path> cluster)
        throws Exception {
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(
            diagnostics, Locale.ROOT, StandardCharsets.UTF_8
        )) {
            JavacTask task = (JavacTask) compiler.getTask(
                null, manager, diagnostics, List.of("--release", "17", "-proc:none"), null,
                manager.getJavaFileObjectsFromPaths(cluster)
            );
            List<CompilationUnitTree> units = new ArrayList<>();
            task.parse().forEach(units::add);
            if (hasErrors(diagnostics)) {
                throw new CompilerFailure(firstDiagnostic(root, diagnostics), true);
            }
            Set<String> packages = new LinkedHashSet<>();
            for (CompilationUnitTree unit : units) {
                packages.add(unit.getPackageName() == null ? "" : unit.getPackageName().toString());
            }
            if (packages.size() != 1 || packages.contains("")) {
                throw new Outcome(terminalPayloadRaw(
                    "unsupported", "defer_package_topology", "mixed_or_default_package",
                    "Selected Java files must declare one named package."
                ), 0);
            }
            return packages.iterator().next();
        }
    }

    private static Path sourceRoot(Path parent, String packageName) throws Outcome {
        Path root = parent;
        String[] parts = packageName.split("\\.");
        for (int index = parts.length - 1; index >= 0; index--) {
            if (root == null || root.getFileName() == null
                || !root.getFileName().toString().equals(parts[index])) {
                throw new Outcome(terminalPayloadRaw(
                    "unsupported", "defer_package_topology", "package_path_mismatch",
                    "Package declaration does not match the parent directory path."
                ), 0);
            }
            root = root.getParent();
        }
        return root;
    }

    private static List<Path> collectCurrentSourceRoot(
        Path projectRoot,
        Path sourceRoot,
        List<Blocker> blockers
    ) throws IOException {
        List<Path> sources = new ArrayList<>();
        Files.walkFileTree(sourceRoot, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attributes) {
                if (!dir.equals(sourceRoot) && Files.isSymbolicLink(dir)) {
                    blockers.add(new Blocker(
                        "symlink_source_ambiguity", relative(projectRoot, dir), 0,
                        "Current-source-root analysis never follows directory symlinks."
                    ));
                    return FileVisitResult.SKIP_SUBTREE;
                }
                if (!dir.equals(sourceRoot) && excludedKind(projectRoot, dir) != null) {
                    return FileVisitResult.SKIP_SUBTREE;
                }
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attributes) {
                if (!file.getFileName().toString().endsWith(".java")) return FileVisitResult.CONTINUE;
                if (Files.isSymbolicLink(file)) {
                    blockers.add(new Blocker(
                        "symlink_source_ambiguity", relative(projectRoot, file), 0,
                        "Current-source-root analysis never reads source symlinks."
                    ));
                } else if (excludedKind(projectRoot, file) == null) {
                    sources.add(file.toAbsolutePath().normalize());
                }
                return FileVisitResult.CONTINUE;
            }
        });
        sources.sort(Comparator.comparing(path -> relative(projectRoot, path)));
        return sources;
    }

    private static List<Blocker> excludedAmbiguities(
        Path root,
        Path sourceRoot,
        String oldPackage,
        Set<String> selectedNames
    ) throws IOException {
        List<Blocker> blockers = new ArrayList<>();
        Files.walkFileTree(root, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attributes) {
                if (!dir.equals(root) && (Files.isSymbolicLink(dir) || pruned(root, dir))) {
                    return FileVisitResult.SKIP_SUBTREE;
                }
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attributes) throws IOException {
                if (Files.isSymbolicLink(file) || !file.getFileName().toString().endsWith(".java")) {
                    return FileVisitResult.CONTINUE;
                }
                String kind = excludedKind(root, file);
                if (kind == null) return FileVisitResult.CONTINUE;
                String text = Files.readString(file, StandardCharsets.UTF_8);
                if (!containsIdentity(text, oldPackage, selectedNames)) return FileVisitResult.CONTINUE;
                blockers.add(new Blocker(
                    kind + "_source_ambiguity", relative(root, file), firstIdentityLine(text, oldPackage, selectedNames),
                    kind + " source mentions the moving package or type and is outside current-source-root compiler coverage."
                ));
                return FileVisitResult.CONTINUE;
            }
        });
        return blockers;
    }

    private static boolean containsIdentity(String text, String packageName, Set<String> names) {
        if (text.contains(packageName)) return true;
        for (String name : names) {
            if (Pattern.compile("(?<![A-Za-z0-9_$])" + Pattern.quote(name) + "(?![A-Za-z0-9_$])")
                .matcher(text).find()) return true;
        }
        return false;
    }

    private static int firstIdentityLine(String text, String packageName, Set<String> names) {
        String[] lines = text.split("\\R", -1);
        for (int index = 0; index < lines.length; index++) {
            if (containsIdentity(lines[index], packageName, names)) return index + 1;
        }
        return 0;
    }

    private static Parsed parseAndAnalyze(JavaCompiler compiler, Path root, List<Path> sources)
        throws Exception {
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        StandardJavaFileManager manager = compiler.getStandardFileManager(
            diagnostics, Locale.ROOT, StandardCharsets.UTF_8
        );
        try {
            JavacTask task = (JavacTask) compiler.getTask(
                null, manager, diagnostics, List.of("--release", "17", "-proc:none"), null,
                manager.getJavaFileObjectsFromPaths(sources)
            );
            List<CompilationUnitTree> units = new ArrayList<>();
            task.parse().forEach(units::add);
            if (hasErrors(diagnostics)) {
                throw new CompilerFailure(firstDiagnostic(root, diagnostics), true);
            }
            task.analyze();
            if (hasErrors(diagnostics)) {
                throw new CompilerFailure(firstDiagnostic(root, diagnostics), false);
            }
            Map<URI, Path> paths = new HashMap<>();
            for (Path source : sources) paths.put(source.toUri(), source);
            return new Parsed(units, Trees.instance(task), paths, diagnostics, manager);
        } catch (Exception error) {
            manager.close();
            throw error;
        }
    }

    private static void validatePackageTopology(
        Path root,
        Path sourceRoot,
        String oldPackage,
        List<Path> sources,
        List<CompilationUnitTree> units,
        Map<URI, Path> paths,
        List<Blocker> blockers
    ) {
        Map<Path, String> packages = new HashMap<>();
        for (CompilationUnitTree unit : units) {
            packages.put(
                paths.get(unit.getSourceFile().toUri()),
                unit.getPackageName() == null ? "" : unit.getPackageName().toString()
            );
        }
        for (Path source : sources) {
            String declared = packages.get(source);
            String expected = packageFromPath(sourceRoot.relativize(source.getParent()));
            if (!declared.equals(expected)) {
                blockers.add(new Blocker(
                    "package_path_mismatch", relative(root, source), 1,
                    "Declared package " + declared + " does not match source-root path " + expected + "."
                ));
            }
        }
    }

    private static String packageFromPath(Path relative) {
        List<String> parts = new ArrayList<>();
        for (Path part : relative) parts.add(part.toString());
        return String.join(".", parts);
    }

    private static List<String> publicTopLevelTypes(CompilationUnitTree unit, Trees trees) {
        List<String> names = new ArrayList<>();
        for (Tree declaration : unit.getTypeDecls()) {
            TreePath path = TreePath.getPath(unit, declaration);
            Element element = path == null ? null : trees.getElement(path);
            if (element instanceof TypeElement type
                && type.getEnclosingElement() instanceof PackageElement
                && type.getModifiers().contains(Modifier.PUBLIC)) {
                names.add(type.getSimpleName().toString());
            }
        }
        names.sort(String::compareTo);
        return names;
    }

    private static List<Impact> impacts(
        Path root,
        List<CompilationUnitTree> units,
        Map<URI, Path> paths,
        Trees trees,
        Set<Path> selectedPaths,
        Set<String> selectedQualified,
        String oldPackage,
        String newPackage,
        List<Blocker> blockers
    ) {
        List<Impact> impacts = new ArrayList<>();
        for (CompilationUnitTree unit : units) {
            Path file = paths.get(unit.getSourceFile().toUri());
            boolean callerSelected = selectedPaths.contains(file);
            String callerPackage = unit.getPackageName() == null ? "" : unit.getPackageName().toString();
            Set<String> wildcardReferencedTypes = referencedTopLevelTypes(unit, trees, oldPackage);
            boolean wildcardUsesSelected = wildcardReferencedTypes.stream().anyMatch(selectedQualified::contains);
            boolean wildcardUsesRetained = wildcardReferencedTypes.stream().anyMatch(
                name -> !selectedQualified.contains(name)
            );
            if (callerSelected) {
                long start = trees.getSourcePositions().getStartPosition(unit, unit.getPackageName());
                impacts.add(impact(
                    root, unit, file, start, "package_declaration", oldPackage, newPackage,
                    "Move the selected compilation unit into the approved subpackage."
                ));
            }
            new TreePathScanner<Void, Void>() {
                @Override
                public Void visitImport(ImportTree tree, Void unused) {
                    String current = tree.getQualifiedIdentifier().toString();
                    TreePath importedPath = TreePath.getPath(unit, tree.getQualifiedIdentifier());
                    Element element = importedPath == null ? null : trees.getElement(importedPath);
                    TypeElement owner = owningTopLevelType(element);
                    if (tree.isStatic()
                        && tree.getQualifiedIdentifier() instanceof MemberSelectTree member) {
                        TreePath ownerPath = TreePath.getPath(unit, member.getExpression());
                        Element ownerElement = ownerPath == null ? null : trees.getElement(ownerPath);
                        if (ownerElement instanceof TypeElement type) owner = type;
                    }
                    String ownerName = owner == null ? "" : owner.getQualifiedName().toString();
                    if (tree.isStatic() && selectedQualified.contains(ownerName)) {
                        add(tree, "static_import", current, replacePackage(current, oldPackage, newPackage),
                            "Static member owner moves with its selected top-level type.");
                    } else if (!tree.isStatic() && element instanceof TypeElement type
                        && selectedQualified.contains(type.getQualifiedName().toString())) {
                        add(tree, "type_import", current, replacePackage(current, oldPackage, newPackage),
                            "Imported selected type moves to the approved subpackage.");
                    } else if (!tree.isStatic() && current.equals(oldPackage + ".*")) {
                        if (wildcardUsesSelected && wildcardUsesRetained) {
                            long start = trees.getSourcePositions().getStartPosition(unit, tree);
                            blockers.add(new Blocker(
                                "wildcard_import_split_required", relative(root, file), line(unit, start),
                                "This wildcard supplies both moving and retained types; split it into explicit imports before the move."
                            ));
                        } else if (wildcardUsesSelected) {
                            add(tree, "wildcard_import", current, newPackage + ".*",
                                "All compiler-resolved types supplied by this wildcard move to the approved subpackage.");
                        }
                    }
                    return null;
                }

                @Override
                public Void visitMemberSelect(MemberSelectTree tree, Void unused) {
                    Element element = trees.getElement(getCurrentPath());
                    if (element instanceof TypeElement type) {
                        String qualified = type.getQualifiedName().toString();
                        if (selectedQualified.contains(qualified) && tree.toString().equals(qualified)) {
                            add(tree, "fully_qualified_type", qualified,
                                replacePackage(qualified, oldPackage, newPackage),
                                "Fully-qualified selected type identity changes with the move.");
                        }
                    }
                    samePackage(tree, element);
                    return super.visitMemberSelect(tree, unused);
                }

                @Override
                public Void visitIdentifier(com.sun.source.tree.IdentifierTree tree, Void unused) {
                    samePackage(tree, trees.getElement(getCurrentPath()));
                    return super.visitIdentifier(tree, unused);
                }

                private void samePackage(Tree tree, Element element) {
                    if (insideImport(getCurrentPath()) || element == null) return;
                    TypeElement owner = owningTopLevelType(element);
                    if (owner == null || !packageName(owner).equals(oldPackage)) return;
                    TreePath declaration = trees.getPath(owner);
                    if (declaration == null) return;
                    Path ownerFile = paths.get(declaration.getCompilationUnit().getSourceFile().toUri());
                    boolean ownerSelected = selectedPaths.contains(ownerFile);
                    if (ownerSelected == callerSelected || !callerPackage.equals(oldPackage)) return;
                    long start = trees.getSourcePositions().getStartPosition(unit, tree);
                    int line = line(unit, start);
                    if (!publicAcrossPackage(element, owner)) {
                        blockers.add(new Blocker(
                            "package_private_cross_boundary", relative(root, file), line,
                            "Moving " + owner.getQualifiedName() + " crosses a non-public same-package reference."
                        ));
                        return;
                    }
                    String kind = callerSelected
                        ? "add_import_from_old_package" : "add_import_to_new_package";
                    String proposed = "import "
                        + (callerSelected ? oldPackage : newPackage)
                        + "." + owner.getSimpleName() + ";";
                    impacts.add(new Impact(
                        relative(root, file), line, kind, owner.getSimpleName().toString(),
                        proposed, "compiler-resolved",
                        "The current same-package reference becomes cross-package after the move."
                    ));
                }

                private void add(Tree tree, String kind, String current, String proposed, String note) {
                    long start = trees.getSourcePositions().getStartPosition(unit, tree);
                    impacts.add(impact(root, unit, file, start, kind, current, proposed, note));
                }
            }.scan(unit, null);
        }
        return deduplicateImpacts(impacts);
    }

    private static Set<String> referencedTopLevelTypes(
        CompilationUnitTree unit, Trees trees, String packageName
    ) {
        Set<String> referenced = new LinkedHashSet<>();
        new TreePathScanner<Void, Void>() {
            @Override
            public Void visitImport(ImportTree tree, Void unused) {
                return null;
            }

            @Override
            public Void visitIdentifier(com.sun.source.tree.IdentifierTree tree, Void unused) {
                add(trees.getElement(getCurrentPath()));
                return super.visitIdentifier(tree, unused);
            }

            @Override
            public Void visitMemberSelect(MemberSelectTree tree, Void unused) {
                add(trees.getElement(getCurrentPath()));
                return super.visitMemberSelect(tree, unused);
            }

            private void add(Element element) {
                TypeElement owner = owningTopLevelType(element);
                if (owner != null && packageName(owner).equals(packageName)) {
                    referenced.add(owner.getQualifiedName().toString());
                }
            }
        }.scan(unit, null);
        return referenced;
    }

    private static boolean insideImport(TreePath path) {
        TreePath current = path;
        while (current != null) {
            if (current.getLeaf() instanceof ImportTree) return true;
            current = current.getParentPath();
        }
        return false;
    }

    private static boolean publicAcrossPackage(Element element, TypeElement owner) {
        if (!owner.getModifiers().contains(Modifier.PUBLIC)) return false;
        if (element == owner) return true;
        return element.getModifiers().contains(Modifier.PUBLIC);
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

    private static String packageName(TypeElement type) {
        Element current = type.getEnclosingElement();
        return current instanceof PackageElement pkg ? pkg.getQualifiedName().toString() : "";
    }

    private static String replacePackage(String value, String oldPackage, String newPackage) {
        return value.startsWith(oldPackage) ? newPackage + value.substring(oldPackage.length()) : value;
    }

    private static Impact impact(
        Path root,
        CompilationUnitTree unit,
        Path file,
        long start,
        String kind,
        String current,
        String proposed,
        String note
    ) {
        return new Impact(
            relative(root, file), line(unit, start), kind, current, proposed,
            "compiler-resolved", note
        );
    }

    private static List<Impact> deduplicateImpacts(List<Impact> impacts) {
        Map<String, Impact> unique = new LinkedHashMap<>();
        impacts.stream().sorted(
            Comparator.comparing(Impact::file).thenComparingInt(Impact::line)
                .thenComparing(Impact::kind).thenComparing(Impact::proposed)
        ).forEach(impact -> unique.put(
            impact.file + ":" + impact.line + ":" + impact.kind + ":" + impact.proposed,
            impact
        ));
        return new ArrayList<>(unique.values());
    }

    private static boolean generated(Path path) throws IOException {
        String text = Files.readString(path, StandardCharsets.UTF_8);
        String head = text.lines().limit(20).reduce("", (left, right) -> left + "\n" + right);
        return (head.contains("Generated") && head.contains("DO NOT EDIT"))
            || GENERATED_ANNOTATION.matcher(head).find();
    }

    private static boolean pruned(Path root, Path path) {
        for (Path part : root.relativize(path.toAbsolutePath().normalize())) {
            if (PRUNE.contains(part.toString().toLowerCase(Locale.ROOT))) return true;
        }
        return false;
    }

    private static String excludedKind(Path root, Path path) {
        Set<String> parts = new LinkedHashSet<>();
        for (Path part : root.relativize(path.toAbsolutePath().normalize())) {
            parts.add(part.toString().toLowerCase(Locale.ROOT));
        }
        String name = path.getFileName() == null ? "" : path.getFileName().toString().toLowerCase(Locale.ROOT);
        if (!disjoint(parts, BUILD)) return "build";
        if (!disjoint(parts, GENERATED)) return "generated";
        if (!disjoint(parts, TEST) || name.endsWith("test.java") || name.endsWith("tests.java")) return "test";
        if (!disjoint(parts, VENDOR)) return "vendor";
        return null;
    }

    private static boolean disjoint(Set<String> left, Set<String> right) {
        for (String value : left) if (right.contains(value)) return false;
        return true;
    }

    private static boolean traversesSymlink(Path root, Path path) {
        if (!path.startsWith(root)) return true;
        Path current = root;
        for (Path part : root.relativize(path)) {
            current = current.resolve(part);
            if (Files.exists(current, LinkOption.NOFOLLOW_LINKS) && Files.isSymbolicLink(current)) {
                return true;
            }
        }
        return false;
    }

    private static boolean hasErrors(DiagnosticCollector<JavaFileObject> diagnostics) {
        return diagnostics.getDiagnostics().stream()
            .anyMatch(item -> item.getKind() == Diagnostic.Kind.ERROR);
    }

    private static String firstDiagnostic(
        Path root,
        DiagnosticCollector<JavaFileObject> diagnostics
    ) {
        return diagnostics.getDiagnostics().stream()
            .filter(item -> item.getKind() == Diagnostic.Kind.ERROR)
            .findFirst()
            .map(item -> {
                String source = item.getSource() == null
                    ? "<compiler>"
                    : relative(root, Path.of(item.getSource().toUri()));
                return source + ":" + item.getLineNumber() + ": " + item.getMessage(Locale.ROOT);
            })
            .orElse("Java compiler evidence is incomplete.");
    }

    private static int line(CompilationUnitTree unit, long position) {
        return position < 0 ? 0 : Math.toIntExact(unit.getLineMap().getLineNumber(position));
    }

    private static Map<String, Object> judgment(Options options) {
        return mapOf(
            "cluster", options.clusterJudgment,
            "project_convention", options.conventionJudgment,
            "framework_convention_inferred", false
        );
    }

    private static Map<String, Object> terminalPayload(
        Options options,
        String status,
        String recommendation,
        String failureKind,
        String message
    ) {
        Map<String, Object> payload = terminalPayloadRaw(
            status, recommendation, failureKind, message
        );
        payload.put("judgment", judgment(options));
        payload.put("parent", relative(options.root, options.parent));
        payload.put("prefix", options.prefix);
        return payload;
    }

    private static Map<String, Object> terminalPayloadRaw(
        String status,
        String recommendation,
        String failureKind,
        String message
    ) {
        return mapOf(
            "schema_version", 1,
            "skill", "propose-folder-reorganization",
            "language", "java",
            "status", status,
            "recommendation", recommendation,
            "failure_kind", failureKind,
            "message", message,
            "read_only", true,
            "analyzer", "jdk-compiler-tree-type-api",
            "moves", List.of(),
            "impacts", List.of(),
            "blockers", List.of(mapOf("kind", failureKind, "file", "", "line", 0, "reason", message))
        );
    }

    private static Map<String, Object> moveMap(Move move) {
        return mapOf(
            "current", move.current,
            "proposed", move.proposed,
            "public_types", move.publicTypes
        );
    }

    private static Map<String, Object> impactMap(Impact impact) {
        return mapOf(
            "file", impact.file,
            "line", impact.line,
            "kind", impact.kind,
            "current", impact.current,
            "proposed", impact.proposed,
            "resolution", impact.resolution,
            "note", impact.note
        );
    }

    private static Map<String, Object> blockerMap(Blocker blocker) {
        return mapOf(
            "kind", blocker.kind,
            "file", blocker.file,
            "line", blocker.line,
            "reason", blocker.reason
        );
    }

    private static void writeArtifacts(Options options, Map<String, Object> payload)
        throws IOException {
        writeAtomic(options.inspection, json(payload) + "\n");
        writeAtomic(options.proposal, renderProposal(payload));
        System.out.println(
            "wrote " + relative(options.root, options.inspection) + " and "
                + relative(options.root, options.proposal) + " (" + payload.get("status") + ")"
        );
    }

    private static String renderProposal(Map<String, Object> payload) {
        String status = String.valueOf(payload.get("status"));
        String recommendation = String.valueOf(payload.get("recommendation"));
        StringBuilder out = new StringBuilder();
        out.append("# Java folder reorganization proposal\n\n")
            .append("> Read-only plan; no source edits were applied.\n\n")
            .append("**Status:** `").append(status).append("`  \n")
            .append("**Recommendation:** `").append(recommendation).append("`\n\n")
            .append("## Explicit human judgments\n\n")
            .append("- Cluster: `")
            .append(((Map<?, ?>) payload.getOrDefault("judgment", Map.of())).get("cluster"))
            .append("`\n- Project subpackage convention: `")
            .append(((Map<?, ?>) payload.getOrDefault("judgment", Map.of())).get("project_convention"))
            .append("`\n- No Java framework convention was inferred.\n\n");
        if (!status.equals("ready")) {
            out.append("## Stop condition\n\nNo move plan is safe. ")
                .append(payload.getOrDefault("message", "Resolve every structured blocker and rerun."))
                .append("\n");
            return out.toString();
        }
        out.append("## Package move\n\n")
            .append("`").append(payload.get("old_package")).append("` → `")
            .append(payload.get("new_package")).append("`\n\n")
            .append("| Current file | Proposed file | Public types |\n")
            .append("|---|---|---|\n");
        for (Map<String, Object> move : maps(payload.get("moves"))) {
            out.append("| `").append(move.get("current")).append("` | `")
                .append(move.get("proposed")).append("` | `")
                .append(String.join("`, `", strings(move.get("public_types"))))
                .append("` |\n");
        }
        out.append("\n## Compiler-resolved impact\n\n")
            .append("| File | Line | Kind | Current | Proposed |\n")
            .append("|---|---:|---|---|---|\n");
        for (Map<String, Object> impact : maps(payload.get("impacts"))) {
            out.append("| `").append(impact.get("file")).append("` | ")
                .append(impact.get("line")).append(" | `").append(impact.get("kind"))
                .append("` | `").append(impact.get("current")).append("` | `")
                .append(impact.get("proposed")).append("` |\n");
        }
        out.append("\n## Native compilation and test obligations\n\n")
            .append("1. Before the move, compile the exact current source root with ")
            .append("`javac --release 17 -proc:none -d <classes> <sources>`.\n")
            .append("2. Run the project's existing native test command; no test framework is inferred.\n")
            .append("3. Apply the reviewed move/import rows in a separate change.\n")
            .append("4. Repeat native compilation and the same native test command.\n\n")
            .append("## Stop condition\n\n")
            .append("Every structured impact is addressed, no package-private boundary is crossed, ")
            .append("and native compilation/tests remain green.\n");
        return out.toString();
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> maps(Object value) {
        return (List<Map<String, Object>>) value;
    }

    private static List<String> strings(Object value) {
        List<String> values = new ArrayList<>();
        for (Object item : (List<?>) value) values.add(String.valueOf(item));
        return values;
    }

    private static void writeAtomic(Path path, String contents) throws IOException {
        Files.createDirectories(path.getParent());
        Path temporary = path.resolveSibling(path.getFileName() + ".tmp-" + ProcessHandle.current().pid());
        Files.writeString(temporary, contents, StandardCharsets.UTF_8);
        try {
            Files.move(
                temporary, path, StandardCopyOption.REPLACE_EXISTING,
                StandardCopyOption.ATOMIC_MOVE
            );
        } catch (java.nio.file.AtomicMoveNotSupportedException ignored) {
            Files.move(temporary, path, StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private static String relative(Path root, Path path) {
        Path normalized = path.toAbsolutePath().normalize();
        return normalized.startsWith(root)
            ? root.relativize(normalized).toString().replace('\\', '/')
            : normalized.toString();
    }

    private static String message(Exception error) {
        return error.getMessage() == null ? error.getClass().getSimpleName() : error.getMessage();
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

    private static final class CompilerFailure extends Exception {
        final boolean syntax;

        CompilerFailure(String message, boolean syntax) {
            super(message);
            this.syntax = syntax;
        }
    }
}

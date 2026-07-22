// Emit one bounded Java record-constructor omission shape from compiler facts.
import com.sun.source.tree.BlockTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.ExpressionStatementTree;
import com.sun.source.tree.IdentifierTree;
import com.sun.source.tree.LiteralTree;
import com.sun.source.tree.MethodInvocationTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.NewClassTree;
import com.sun.source.tree.StatementTree;
import com.sun.source.tree.Tree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.TreePath;
import com.sun.source.util.TreePathScanner;
import com.sun.source.util.Trees;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import javax.lang.model.element.Element;
import javax.lang.model.element.ElementKind;
import javax.lang.model.element.ExecutableElement;
import javax.lang.model.element.RecordComponentElement;
import javax.lang.model.element.TypeElement;
import javax.lang.model.element.VariableElement;
import javax.lang.model.type.TypeMirror;
import javax.lang.model.util.Types;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

public class detect_java_incomplete_sweep {
    private record Site(String file, int line, String value) {}
    private record Deferred(String file, int line, String reason, String detail) {}
    private record Candidate(
            String callee,
            String option,
            int optionPosition,
            String defaultValue,
            List<Site> present,
            Site straggler) {}
    private static final class Group {
        final String callee;
        final String option;
        final int optionPosition;
        final List<Site> present = new ArrayList<>();
        final List<Site> stragglers = new ArrayList<>();
        String defaultValue;
        boolean unsafe;

        Group(String callee, String option, int optionPosition) {
            this.callee = callee;
            this.option = option;
            this.optionPosition = optionPosition;
        }
    }

    private static void fail(String message) {
        System.err.println("[detect_java_incomplete_sweep] " + message);
        System.exit(2);
    }

    public static void main(String[] args) throws Exception {
        Path projectRoot = null;
        List<Path> files = new ArrayList<>();
        for (int index = 0; index < args.length; index++) {
            switch (args[index]) {
                case "--project-root" -> projectRoot = Path.of(args[++index]).toAbsolutePath().normalize();
                case "--file" -> files.add(Path.of(args[++index]).toAbsolutePath().normalize());
                default -> fail("unknown argument: " + args[index]);
            }
        }
        if (projectRoot == null || files.isEmpty()) fail("--project-root and at least one --file are required");
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) fail("JDK compiler API is unavailable; a JRE is insufficient");
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(diagnostics, Locale.ROOT, StandardCharsets.UTF_8)) {
            Iterable<? extends JavaFileObject> inputs = manager.getJavaFileObjectsFromPaths(files);
            JavacTask task = (JavacTask) compiler.getTask(
                    null, manager, diagnostics, List.of("-proc:none", "--release", "17"), null, inputs);
            List<CompilationUnitTree> units = new ArrayList<>();
            task.parse().forEach(units::add);
            task.analyze();
            for (Diagnostic<? extends JavaFileObject> diagnostic : diagnostics.getDiagnostics()) {
                if (diagnostic.getKind() == Diagnostic.Kind.ERROR) {
                    String file = diagnostic.getSource() == null
                            ? "<unknown>"
                            : relative(projectRoot, Path.of(diagnostic.getSource().toUri()));
                    fail("syntax-error or unavailable type facts in " + file + ": line "
                            + diagnostic.getLineNumber() + ": " + diagnostic.getMessage(Locale.ROOT));
                }
            }
            Trees trees = Trees.instance(task);
            Types types = task.getTypes();
            Map<String, Group> groups = new LinkedHashMap<>();
            List<Deferred> deferred = new ArrayList<>();
            for (CompilationUnitTree unit : units) {
                new ConstructorScanner(projectRoot, unit, trees, types, groups, deferred).scan(unit, null);
            }
            List<Candidate> candidates = collapse(groups, deferred);
            System.out.println(render(candidates, deferred));
        }
    }

    private static final class ConstructorScanner extends TreePathScanner<Void, Void> {
        private final Path projectRoot;
        private final CompilationUnitTree unit;
        private final Trees trees;
        private final Types types;
        private final Map<String, Group> groups;
        private final List<Deferred> deferred;

        ConstructorScanner(
                Path projectRoot,
                CompilationUnitTree unit,
                Trees trees,
                Types types,
                Map<String, Group> groups,
                List<Deferred> deferred) {
            this.projectRoot = projectRoot;
            this.unit = unit;
            this.trees = trees;
            this.types = types;
            this.groups = groups;
            this.deferred = deferred;
        }

        @Override
        public Void visitNewClass(NewClassTree node, Void unused) {
            Element resolved = trees.getElement(getCurrentPath());
            int line = line(node);
            String file = relative(projectRoot, Path.of(unit.getSourceFile().toUri()));
            if (!(resolved instanceof ExecutableElement constructor)
                    || constructor.getKind() != ElementKind.CONSTRUCTOR
                    || !(constructor.getEnclosingElement() instanceof TypeElement owner)
                    || owner.getKind() != ElementKind.RECORD) {
                return super.visitNewClass(node, unused);
            }
            List<? extends RecordComponentElement> components = owner.getRecordComponents();
            if (components.size() < 2) return super.visitNewClass(node, unused);
            int optionPosition = components.size() - 1;
            String option = components.get(optionPosition).getSimpleName().toString();
            String callee = owner.getQualifiedName().toString();
            Group group = groups.computeIfAbsent(callee, key -> new Group(key, option, optionPosition));
            List<? extends VariableElement> parameters = constructor.getParameters();
            if (isCanonical(parameters, components)) {
                if (node.getArguments().size() != components.size()) {
                    group.unsafe = true;
                    deferred.add(new Deferred(file, line, "unavailable_canonical_argument", callee));
                } else {
                    String value = comparable(node.getArguments().get(optionPosition), components.get(optionPosition).asType());
                    if (value == null) {
                        group.unsafe = true;
                        deferred.add(new Deferred(file, line, "non_comparable_present_value", callee + "." + option));
                    } else {
                        group.present.add(new Site(file, line, value));
                    }
                }
            } else if (isPrefixOverload(parameters, components)) {
                String defaultValue = delegatedDefault(constructor, components);
                if (defaultValue == null) {
                    group.unsafe = true;
                    deferred.add(new Deferred(file, line, "unresolved_record_constructor_default", callee));
                } else {
                    if (group.defaultValue != null && !group.defaultValue.equals(defaultValue)) group.unsafe = true;
                    group.defaultValue = defaultValue;
                    group.stragglers.add(new Site(file, line, ""));
                }
            }
            return super.visitNewClass(node, unused);
        }

        private boolean isCanonical(
                List<? extends VariableElement> parameters,
                List<? extends RecordComponentElement> components) {
            if (parameters.size() != components.size()) return false;
            for (int index = 0; index < components.size(); index++) {
                if (!types.isSameType(parameters.get(index).asType(), components.get(index).asType())) return false;
            }
            return true;
        }

        private boolean isPrefixOverload(
                List<? extends VariableElement> parameters,
                List<? extends RecordComponentElement> components) {
            if (parameters.size() != components.size() - 1) return false;
            for (int index = 0; index < parameters.size(); index++) {
                if (!parameters.get(index).getSimpleName().contentEquals(components.get(index).getSimpleName())
                        || !types.isSameType(parameters.get(index).asType(), components.get(index).asType())) return false;
            }
            return true;
        }

        private String delegatedDefault(
                ExecutableElement constructor,
                List<? extends RecordComponentElement> components) {
            TreePath path = trees.getPath(constructor);
            if (path == null || !(path.getLeaf() instanceof MethodTree method)) return null;
            BlockTree body = method.getBody();
            if (body == null || body.getStatements().isEmpty()) return null;
            StatementTree first = body.getStatements().get(0);
            if (!(first instanceof ExpressionStatementTree statement)
                    || !(statement.getExpression() instanceof MethodInvocationTree invocation)
                    || !(invocation.getMethodSelect() instanceof IdentifierTree identifier)
                    || !identifier.getName().contentEquals("this")
                    || invocation.getArguments().size() != components.size()) return null;
            for (int index = 0; index < components.size() - 1; index++) {
                Tree argument = invocation.getArguments().get(index);
                if (!(argument instanceof IdentifierTree passed)
                        || !passed.getName().contentEquals(components.get(index).getSimpleName())) return null;
            }
            return comparable(
                    invocation.getArguments().get(components.size() - 1),
                    components.get(components.size() - 1).asType());
        }

        private String comparable(Tree tree, TypeMirror type) {
            if (!(tree instanceof LiteralTree literal) || literal.getValue() == null) return null;
            return type.toString() + ":" + literal.getValue();
        }

        private int line(Tree tree) {
            long position = trees.getSourcePositions().getStartPosition(unit, tree);
            return position < 0 ? 0 : (int) unit.getLineMap().getLineNumber(position);
        }
    }

    private static List<Candidate> collapse(Map<String, Group> groups, List<Deferred> deferred) {
        List<Candidate> candidates = new ArrayList<>();
        for (Group group : groups.values()) {
            int total = group.present.size() + group.stragglers.size();
            if (group.unsafe || total < 4 || group.present.size() < 3 || group.stragglers.size() != 1) {
                if (total > 0 && group.stragglers.size() != 1) {
                    Site site = group.stragglers.isEmpty() ? group.present.get(0) : group.stragglers.get(0);
                    deferred.add(new Deferred(site.file(), site.line(), "ambiguous_multiple_stragglers", group.callee));
                }
                continue;
            }
            String value = group.present.get(0).value();
            if (group.present.stream().anyMatch(site -> !site.value().equals(value))) {
                Site site = group.present.get(0);
                deferred.add(new Deferred(site.file(), site.line(), "inconsistent_option_value", group.callee + "." + group.option));
                continue;
            }
            if (value.equals(group.defaultValue)) {
                Site site = group.stragglers.get(0);
                deferred.add(new Deferred(site.file(), site.line(), "present_value_equals_constructor_default", group.callee + "." + group.option));
                continue;
            }
            group.present.sort(Comparator.comparing(Site::file).thenComparingInt(Site::line));
            candidates.add(new Candidate(
                    group.callee, group.option, group.optionPosition, group.defaultValue,
                    List.copyOf(group.present), group.stragglers.get(0)));
        }
        candidates.sort(Comparator.comparing(Candidate::callee));
        deferred.sort(Comparator.comparing(Deferred::file).thenComparingInt(Deferred::line).thenComparing(Deferred::reason));
        return candidates;
    }

    private static String relative(Path root, Path file) {
        return root.relativize(file.toAbsolutePath().normalize()).toString().replace('\\', '/');
    }

    private static String quote(String value) {
        StringBuilder out = new StringBuilder("\"");
        for (char character : value.toCharArray()) {
            switch (character) {
                case '\\' -> out.append("\\\\");
                case '"' -> out.append("\\\"");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> out.append(character);
            }
        }
        return out.append('"').toString();
    }

    private static String render(List<Candidate> candidates, List<Deferred> deferred) {
        StringBuilder out = new StringBuilder("{\"schema_version\":1,\"analyzer\":\"jdk-compiler-tree-direct-record-constructors\",\"candidates\":[");
        for (int index = 0; index < candidates.size(); index++) {
            if (index > 0) out.append(',');
            Candidate candidate = candidates.get(index);
            out.append("{\"callee\":").append(quote(candidate.callee()))
                    .append(",\"option\":").append(quote(candidate.option()))
                    .append(",\"option_position\":").append(candidate.optionPosition())
                    .append(",\"default_value\":").append(quote(candidate.defaultValue()))
                    .append(",\"straggler\":{\"file\":").append(quote(candidate.straggler().file()))
                    .append(",\"line\":").append(candidate.straggler().line()).append("},\"present\":[");
            for (int siteIndex = 0; siteIndex < candidate.present().size(); siteIndex++) {
                if (siteIndex > 0) out.append(',');
                Site site = candidate.present().get(siteIndex);
                out.append("{\"file\":").append(quote(site.file()))
                        .append(",\"line\":").append(site.line())
                        .append(",\"value\":").append(quote(site.value())).append('}');
            }
            out.append("]}");
        }
        out.append("],\"deferred\":[");
        for (int index = 0; index < deferred.size(); index++) {
            if (index > 0) out.append(',');
            Deferred item = deferred.get(index);
            out.append("{\"file\":").append(quote(item.file()))
                    .append(",\"line\":").append(item.line())
                    .append(",\"reason\":").append(quote(item.reason()))
                    .append(",\"detail\":").append(quote(item.detail())).append('}');
        }
        return out.append("]}").toString();
    }
}

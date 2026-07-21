// Emit conservative direct-static-method record-construction pairs from JDK facts.
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.LambdaExpressionTree;
import com.sun.source.tree.MethodInvocationTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.NewClassTree;
import com.sun.source.tree.ReturnTree;
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
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import javax.lang.model.element.Element;
import javax.lang.model.element.ElementKind;
import javax.lang.model.element.ExecutableElement;
import javax.lang.model.element.Modifier;
import javax.lang.model.element.RecordComponentElement;
import javax.lang.model.element.TypeElement;
import javax.lang.model.type.DeclaredType;
import javax.lang.model.type.TypeMirror;
import javax.lang.model.util.Types;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

public class detect_java_semantic {
    private record Caller(String file, int line, String symbol) {}
    private record Deferred(String file, int line, String symbol, String reason) {}
    private static final class MethodFact {
        final ExecutableElement element;
        final String file;
        final String name;
        final int line;
        final int endLine;
        final String returnType;
        final List<String> fields;
        final Set<ExecutableElement> calls = new HashSet<>();
        final List<Caller> callers = new ArrayList<>();

        MethodFact(
                ExecutableElement element,
                String file,
                String name,
                int line,
                int endLine,
                String returnType,
                List<String> fields) {
            this.element = element;
            this.file = file;
            this.name = name;
            this.line = line;
            this.endLine = endLine;
            this.returnType = returnType;
            this.fields = fields;
        }
    }

    private static void fail(String message) {
        System.err.println("[detect_java_semantic] " + message);
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
            List<MethodFact> methods = new ArrayList<>();
            List<Deferred> deferred = new ArrayList<>();
            Map<ExecutableElement, MethodFact> byElement = new HashMap<>();
            for (CompilationUnitTree unit : units) {
                CandidateScanner scanner = new CandidateScanner(projectRoot, unit, trees, types, methods, deferred);
                scanner.scan(unit, null);
            }
            for (MethodFact method : methods) byElement.put(method.element, method);
            for (CompilationUnitTree unit : units) {
                new CallScanner(projectRoot, unit, trees, byElement).scan(unit, null);
            }
            methods.sort(Comparator.comparing((MethodFact item) -> item.name).thenComparingInt(item -> item.line));
            List<MethodFact[]> leads = collapse(methods, deferred);
            System.out.println(render(leads, methods.size(), deferred));
        }
    }

    private static final class CandidateScanner extends TreePathScanner<Void, Void> {
        private final Path root;
        private final CompilationUnitTree unit;
        private final Trees trees;
        private final Types types;
        private final List<MethodFact> methods;
        private final List<Deferred> deferred;

        CandidateScanner(
                Path root,
                CompilationUnitTree unit,
                Trees trees,
                Types types,
                List<MethodFact> methods,
                List<Deferred> deferred) {
            this.root = root;
            this.unit = unit;
            this.trees = trees;
            this.types = types;
            this.methods = methods;
            this.deferred = deferred;
        }

        @Override
        public Void visitMethod(MethodTree node, Void unused) {
            Element resolved = trees.getElement(getCurrentPath());
            if (!(resolved instanceof ExecutableElement method)
                    || method.getKind() != ElementKind.METHOD
                    || !method.getModifiers().contains(Modifier.STATIC)
                    || node.getBody() == null
                    || !(method.getReturnType() instanceof DeclaredType declared)
                    || !(declared.asElement() instanceof TypeElement returnOwner)
                    || returnOwner.getKind() != ElementKind.RECORD) {
                return super.visitMethod(node, unused);
            }
            List<? extends RecordComponentElement> components = returnOwner.getRecordComponents();
            if (components.size() < 2) return super.visitMethod(node, unused);
            ReturnScanner returns = new ReturnScanner(trees, types, returnOwner, components);
            returns.scan(new TreePath(getCurrentPath(), node.getBody()), null);
            String file = relative(root, Path.of(unit.getSourceFile().toUri()));
            int line = line(node);
            String symbol = symbol(method);
            if (returns.returnCount != 1 || !returns.valid) {
                deferred.add(new Deferred(file, line, symbol, "not_one_direct_record_return"));
                return super.visitMethod(node, unused);
            }
            long endPosition = trees.getSourcePositions().getEndPosition(unit, node);
            int endLine = endPosition < 0 ? line : (int) unit.getLineMap().getLineNumber(Math.max(0, endPosition - 1));
            List<String> fields = components.stream().map(item -> item.getSimpleName().toString()).toList();
            methods.add(new MethodFact(
                    method, file, symbol, line, endLine,
                    returnOwner.getQualifiedName().toString(), fields));
            return super.visitMethod(node, unused);
        }

        private int line(Tree tree) {
            long position = trees.getSourcePositions().getStartPosition(unit, tree);
            return position < 0 ? 0 : (int) unit.getLineMap().getLineNumber(position);
        }
    }

    private static final class ReturnScanner extends TreePathScanner<Void, Void> {
        private final Trees trees;
        private final Types types;
        private final TypeElement returnOwner;
        private final List<? extends RecordComponentElement> components;
        int returnCount;
        boolean valid = true;

        ReturnScanner(
                Trees trees,
                Types types,
                TypeElement returnOwner,
                List<? extends RecordComponentElement> components) {
            this.trees = trees;
            this.types = types;
            this.returnOwner = returnOwner;
            this.components = components;
        }

        @Override
        public Void visitReturn(ReturnTree node, Void unused) {
            returnCount++;
            if (!(node.getExpression() instanceof NewClassTree construction)) {
                valid = false;
                return null;
            }
            Element resolved = trees.getElement(new TreePath(getCurrentPath(), construction));
            if (!(resolved instanceof ExecutableElement constructor)
                    || constructor.getKind() != ElementKind.CONSTRUCTOR
                    || !constructor.getEnclosingElement().equals(returnOwner)
                    || constructor.getParameters().size() != components.size()
                    || construction.getArguments().size() != components.size()) {
                valid = false;
                return null;
            }
            for (int index = 0; index < components.size(); index++) {
                if (!types.isSameType(
                        constructor.getParameters().get(index).asType(),
                        components.get(index).asType())) {
                    valid = false;
                }
            }
            return null;
        }

        @Override public Void visitLambdaExpression(LambdaExpressionTree node, Void unused) { return null; }
        @Override public Void visitClass(com.sun.source.tree.ClassTree node, Void unused) { return null; }
    }

    private static final class CallScanner extends TreePathScanner<Void, Void> {
        private final Path root;
        private final CompilationUnitTree unit;
        private final Trees trees;
        private final Map<ExecutableElement, MethodFact> candidates;
        private ExecutableElement current;

        CallScanner(
                Path root,
                CompilationUnitTree unit,
                Trees trees,
                Map<ExecutableElement, MethodFact> candidates) {
            this.root = root;
            this.unit = unit;
            this.trees = trees;
            this.candidates = candidates;
        }

        @Override
        public Void visitMethod(MethodTree node, Void unused) {
            Element resolved = trees.getElement(getCurrentPath());
            ExecutableElement previous = current;
            current = resolved instanceof ExecutableElement method ? method : null;
            super.visitMethod(node, unused);
            current = previous;
            return null;
        }

        @Override
        public Void visitMethodInvocation(MethodInvocationTree node, Void unused) {
            Element resolved = trees.getElement(getCurrentPath());
            if (current != null && resolved instanceof ExecutableElement called) {
                MethodFact owner = candidates.get(current);
                if (owner != null) owner.calls.add(called);
                MethodFact target = candidates.get(called);
                if (target != null) {
                    long position = trees.getSourcePositions().getStartPosition(unit, node);
                    int line = position < 0 ? 0 : (int) unit.getLineMap().getLineNumber(position);
                    target.callers.add(new Caller(
                            relative(root, Path.of(unit.getSourceFile().toUri())), line, symbol(current)));
                }
            }
            return super.visitMethodInvocation(node, unused);
        }
    }

    private static List<MethodFact[]> collapse(List<MethodFact> methods, List<Deferred> deferred) {
        Map<String, List<MethodFact>> byReturn = new LinkedHashMap<>();
        for (MethodFact method : methods) {
            method.callers.sort(Comparator.comparing(Caller::file).thenComparingInt(Caller::line));
            if (method.callers.isEmpty()) {
                deferred.add(new Deferred(method.file, method.line, method.name, "no_resolved_production_caller"));
                continue;
            }
            byReturn.computeIfAbsent(method.returnType, ignored -> new ArrayList<>()).add(method);
        }
        List<MethodFact[]> leads = new ArrayList<>();
        for (List<MethodFact> group : byReturn.values()) {
            for (int leftIndex = 0; leftIndex < group.size(); leftIndex++) {
                for (int rightIndex = leftIndex + 1; rightIndex < group.size(); rightIndex++) {
                    MethodFact left = group.get(leftIndex);
                    MethodFact right = group.get(rightIndex);
                    if (left.calls.contains(right.element) || right.calls.contains(left.element)) {
                        deferred.add(new Deferred(left.file, left.line, left.name, "resolved_caller_callee_pair"));
                        continue;
                    }
                    leads.add(new MethodFact[] {left, right});
                }
            }
        }
        deferred.sort(Comparator.comparing(Deferred::file).thenComparingInt(Deferred::line).thenComparing(Deferred::reason));
        return leads;
    }

    private static String symbol(ExecutableElement method) {
        TypeElement owner = (TypeElement) method.getEnclosingElement();
        return owner.getQualifiedName() + "." + method.getSimpleName();
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

    private static void renderMember(StringBuilder out, MethodFact method) {
        out.append("{\"file\":").append(quote(method.file))
                .append(",\"qualified_name\":").append(quote(method.name))
                .append(",\"line\":").append(method.line)
                .append(",\"end_line\":").append(method.endLine)
                .append(",\"caller_count\":").append(method.callers.size())
                .append(",\"direct_callers\":[");
        for (int index = 0; index < method.callers.size(); index++) {
            if (index > 0) out.append(',');
            Caller caller = method.callers.get(index);
            out.append("{\"file\":").append(quote(caller.file()))
                    .append(",\"line\":").append(caller.line())
                    .append(",\"symbol\":").append(quote(caller.symbol())).append('}');
        }
        out.append("]}");
    }

    private static String render(List<MethodFact[]> leads, int eligibleCount, List<Deferred> deferred) {
        StringBuilder out = new StringBuilder("{\"schema_version\":1,\"analyzer\":\"jdk-compiler-tree-static-record-returns\",\"eligible_method_count\":")
                .append(eligibleCount).append(",\"leads\":[");
        for (int index = 0; index < leads.size(); index++) {
            if (index > 0) out.append(',');
            MethodFact left = leads.get(index)[0];
            MethodFact right = leads.get(index)[1];
            out.append("{\"static_return_type\":").append(quote(left.returnType))
                    .append(",\"return_fields\":[");
            for (int fieldIndex = 0; fieldIndex < left.fields.size(); fieldIndex++) {
                if (fieldIndex > 0) out.append(',');
                out.append(quote(left.fields.get(fieldIndex)));
            }
            out.append("],\"members\":[");
            renderMember(out, left);
            out.append(',');
            renderMember(out, right);
            out.append("]}");
        }
        out.append("],\"deferred\":[");
        for (int index = 0; index < deferred.size(); index++) {
            if (index > 0) out.append(',');
            Deferred item = deferred.get(index);
            out.append("{\"file\":").append(quote(item.file()))
                    .append(",\"line\":").append(item.line())
                    .append(",\"symbol\":").append(quote(item.symbol()))
                    .append(",\"reason\":").append(quote(item.reason())).append('}');
        }
        return out.append("]}").toString();
    }
}

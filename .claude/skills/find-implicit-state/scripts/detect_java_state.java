// Emit compiler-attributed direct Java String-field literal operations.
//
// This helper is intentionally family-local. It uses only the host JDK's
// compiler-tree and type APIs; it does not invoke a build tool or load a JAR.
import com.sun.source.tree.AssignmentTree;
import com.sun.source.tree.BinaryTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.ExpressionTree;
import com.sun.source.tree.LiteralTree;
import com.sun.source.tree.MemberSelectTree;
import com.sun.source.tree.MethodInvocationTree;
import com.sun.source.tree.ParenthesizedTree;
import com.sun.source.tree.Tree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.TreePath;
import com.sun.source.util.TreePathScanner;
import com.sun.source.util.Trees;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import javax.lang.model.element.Element;
import javax.lang.model.element.ElementKind;
import javax.lang.model.element.NestingKind;
import javax.lang.model.element.PackageElement;
import javax.lang.model.element.TypeElement;
import javax.lang.model.element.VariableElement;
import javax.lang.model.type.TypeMirror;
import javax.lang.model.util.Elements;
import javax.lang.model.util.Types;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

public class detect_java_state {
    private record FieldFact(
            String owner,
            String packageName,
            String field,
            String declarationFile,
            long declarationLine) {}

    private record Operation(
            String file,
            long line,
            long column,
            String evidence,
            String operation,
            String literal,
            boolean unsafeReferenceEquality,
            FieldFact authority) {}

    private record Outcome(String status, List<String> diagnostics, List<Operation> operations) {}

    private static void fail(String message) {
        System.err.println("[detect_java_state] " + message);
        System.exit(2);
    }

    public static void main(String[] args) throws Exception {
        if (Runtime.version().feature() < 17) {
            fail("Java 17 or newer is required");
        }
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) {
            fail("JDK compiler API is unavailable; a JRE is insufficient");
        }
        Path projectRoot = null;
        List<Path> files = new ArrayList<>();
        for (int index = 0; index < args.length; index++) {
            switch (args[index]) {
                case "--project-root" -> {
                    if (++index >= args.length) fail("--project-root requires a path");
                    projectRoot = Path.of(args[index]).toAbsolutePath().normalize();
                }
                case "--file" -> {
                    if (++index >= args.length) fail("--file requires a path");
                    files.add(Path.of(args[index]).toAbsolutePath().normalize());
                }
                default -> fail("unknown argument: " + args[index]);
            }
        }
        if (projectRoot == null || files.isEmpty()) {
            fail("usage: detect_java_state.java --project-root <root> --file <source> [--file <source> ...]");
        }
        System.out.println(render(analyze(projectRoot, files, compiler)));
    }

    private static Outcome analyze(Path root, List<Path> files, JavaCompiler compiler) throws Exception {
        for (Path file : files) {
            if (!file.startsWith(root) || !file.getFileName().toString().endsWith(".java")) {
                return new Outcome("invalid-source", List.of("source is outside project root or not .java: " + file), List.of());
            }
        }
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(
                diagnostics, Locale.ROOT, StandardCharsets.UTF_8)) {
            JavacTask task = (JavacTask) compiler.getTask(
                    null,
                    manager,
                    diagnostics,
                    List.of("--release", "17", "-proc:none", "-Xlint:none"),
                    null,
                    manager.getJavaFileObjectsFromPaths(files));
            List<CompilationUnitTree> units = new ArrayList<>();
            task.parse().forEach(units::add);
            List<String> parseErrors = errorMessages(root, diagnostics);
            if (!parseErrors.isEmpty()) {
                return new Outcome("syntax-error", parseErrors, List.of());
            }
            try {
                task.analyze();
            } catch (RuntimeException error) {
                return new Outcome("partial", List.of("compiler attribution failed: " + error.getMessage()), List.of());
            }
            List<String> attributionErrors = errorMessages(root, diagnostics);
            if (!attributionErrors.isEmpty()) {
                return new Outcome("partial", attributionErrors, List.of());
            }
            Map<URI, Path> paths = new HashMap<>();
            for (Path file : files) paths.put(file.toUri(), file);
            Trees trees = Trees.instance(task);
            Elements elements = task.getElements();
            TypeElement stringElement = elements.getTypeElement("java.lang.String");
            if (stringElement == null) {
                return new Outcome("partial", List.of("java.lang.String type facts are unavailable"), List.of());
            }
            Collector collector = new Collector(root, paths, trees, task.getTypes(), elements, stringElement.asType());
            for (CompilationUnitTree unit : units) collector.scan(unit, null);
            collector.operations.sort(Comparator
                    .comparing(Operation::file)
                    .thenComparingLong(Operation::line)
                    .thenComparingLong(Operation::column)
                    .thenComparing(Operation::operation)
                    .thenComparing(Operation::literal));
            return new Outcome("complete", List.of(), collector.operations);
        }
    }

    private static List<String> errorMessages(Path root, DiagnosticCollector<JavaFileObject> diagnostics) {
        return diagnostics.getDiagnostics().stream()
                .filter(item -> item.getKind() == Diagnostic.Kind.ERROR)
                .map(item -> {
                    String file = item.getSource() == null
                            ? "<compiler>"
                            : relative(root, Path.of(item.getSource().toUri()));
                    return file + ":" + item.getLineNumber() + ": " + item.getMessage(Locale.ROOT);
                })
                .distinct()
                .toList();
    }

    private static final class Collector extends TreePathScanner<Void, Void> {
        private final Path root;
        private final Map<URI, Path> paths;
        private final Trees trees;
        private final Types types;
        private final Elements elements;
        private final TypeMirror stringType;
        private final List<Operation> operations = new ArrayList<>();
        private CompilationUnitTree unit;
        private Path file;

        private Collector(
                Path root,
                Map<URI, Path> paths,
                Trees trees,
                Types types,
                Elements elements,
                TypeMirror stringType) {
            this.root = root;
            this.paths = paths;
            this.trees = trees;
            this.types = types;
            this.elements = elements;
            this.stringType = stringType;
        }

        @Override
        public Void visitCompilationUnit(CompilationUnitTree node, Void unused) {
            unit = node;
            file = paths.get(node.getSourceFile().toUri());
            return super.visitCompilationUnit(node, unused);
        }

        @Override
        public Void visitAssignment(AssignmentTree node, Void unused) {
            FieldFact field = directStringField(node.getVariable());
            String literal = stringLiteral(node.getExpression());
            if (field != null && literal != null) emit(node, field, literal, "assignment", false);
            return super.visitAssignment(node, unused);
        }

        @Override
        public Void visitBinary(BinaryTree node, Void unused) {
            if (node.getKind() == Tree.Kind.EQUAL_TO || node.getKind() == Tree.Kind.NOT_EQUAL_TO) {
                FieldFact left = directStringField(node.getLeftOperand());
                FieldFact right = directStringField(node.getRightOperand());
                String leftLiteral = stringLiteral(node.getLeftOperand());
                String rightLiteral = stringLiteral(node.getRightOperand());
                if (left != null && rightLiteral != null) {
                    emit(node, left, rightLiteral, "reference_equality", true);
                }
                if (right != null && leftLiteral != null) {
                    emit(node, right, leftLiteral, "reference_equality", true);
                }
            }
            return super.visitBinary(node, unused);
        }

        @Override
        public Void visitMethodInvocation(MethodInvocationTree node, Void unused) {
            Element invoked = trees.getElement(getCurrentPath());
            if (invoked instanceof javax.lang.model.element.ExecutableElement method) {
                String owner = ownerName(method.getEnclosingElement());
                if (owner.equals("java.lang.String") && method.getSimpleName().contentEquals("equals")
                        && node.getArguments().size() == 1
                        && node.getMethodSelect() instanceof MemberSelectTree select) {
                    FieldFact receiver = directStringField(select.getExpression());
                    String argumentLiteral = stringLiteral(node.getArguments().get(0));
                    if (receiver != null && argumentLiteral != null) {
                        emit(node, receiver, argumentLiteral, "string_equals", false);
                    }
                    FieldFact argument = directStringField(node.getArguments().get(0));
                    String receiverLiteral = stringLiteral(select.getExpression());
                    if (argument != null && receiverLiteral != null) {
                        emit(node, argument, receiverLiteral, "string_equals", false);
                    }
                }
                if (owner.equals("java.util.Objects") && method.getSimpleName().contentEquals("equals")
                        && node.getArguments().size() == 2) {
                    FieldFact first = directStringField(node.getArguments().get(0));
                    FieldFact second = directStringField(node.getArguments().get(1));
                    String firstLiteral = stringLiteral(node.getArguments().get(0));
                    String secondLiteral = stringLiteral(node.getArguments().get(1));
                    if (first != null && secondLiteral != null) emit(node, first, secondLiteral, "objects_equals", false);
                    if (second != null && firstLiteral != null) emit(node, second, firstLiteral, "objects_equals", false);
                }
            }
            return super.visitMethodInvocation(node, unused);
        }

        private void emit(Tree node, FieldFact field, String literal, String operation, boolean unsafe) {
            long start = trees.getSourcePositions().getStartPosition(unit, node);
            if (start < 0 || file == null) return;
            long line = unit.getLineMap().getLineNumber(start);
            long column = unit.getLineMap().getColumnNumber(start);
            String evidence;
            try {
                List<String> lines = java.nio.file.Files.readAllLines(file, StandardCharsets.UTF_8);
                evidence = line > 0 && line <= lines.size() ? lines.get((int) line - 1).trim() : "";
            } catch (Exception error) {
                evidence = "";
            }
            operations.add(new Operation(
                    relative(root, file), line, column, evidence, operation, literal, unsafe, field));
        }

        private FieldFact directStringField(ExpressionTree expression) {
            ExpressionTree unwrapped = unwrap(expression);
            TreePath path = new TreePath(getCurrentPath(), unwrapped);
            Element element = trees.getElement(path);
            if (!(element instanceof VariableElement field) || field.getKind() != ElementKind.FIELD) return null;
            if (!types.isSameType(types.erasure(field.asType()), types.erasure(stringType))) return null;
            Element enclosing = field.getEnclosingElement();
            if (!(enclosing instanceof TypeElement owner) || owner.getNestingKind() != NestingKind.TOP_LEVEL) return null;
            TreePath declaration = trees.getPath(field);
            if (declaration == null || declaration.getCompilationUnit() == null) return null;
            Path declarationPath = paths.get(declaration.getCompilationUnit().getSourceFile().toUri());
            if (declarationPath == null) return null;
            long start = trees.getSourcePositions().getStartPosition(declaration.getCompilationUnit(), declaration.getLeaf());
            long declarationLine = start < 0 ? 0 : declaration.getCompilationUnit().getLineMap().getLineNumber(start);
            PackageElement pkg = elements.getPackageOf(owner);
            return new FieldFact(
                    owner.getQualifiedName().toString(),
                    pkg == null ? "" : pkg.getQualifiedName().toString(),
                    field.getSimpleName().toString(),
                    relative(root, declarationPath),
                    declarationLine);
        }

        private static ExpressionTree unwrap(ExpressionTree expression) {
            ExpressionTree current = expression;
            while (current instanceof ParenthesizedTree parenthesized) current = parenthesized.getExpression();
            return current;
        }

        private static String stringLiteral(ExpressionTree expression) {
            ExpressionTree current = unwrap(expression);
            if (current instanceof LiteralTree literal && literal.getValue() instanceof String value) return value;
            return null;
        }
    }

    private static String ownerName(Element element) {
        return element instanceof TypeElement type ? type.getQualifiedName().toString() : "";
    }

    private static String relative(Path root, Path file) {
        try {
            return root.relativize(file).toString().replace('\\', '/');
        } catch (IllegalArgumentException error) {
            return file.toString().replace('\\', '/');
        }
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
                default -> {
                    if (character < 0x20) out.append(String.format("\\u%04x", (int) character));
                    else out.append(character);
                }
            }
        }
        return out.append('"').toString();
    }

    private static String render(Outcome outcome) {
        StringBuilder out = new StringBuilder("{\"schema_version\":1,\"analyzer\":\"jdk-compiler-tree-type-api\",\"java_version\":")
                .append(quote(System.getProperty("java.version")))
                .append(",\"status\":").append(quote(outcome.status())).append(",\"diagnostics\":[");
        for (int index = 0; index < outcome.diagnostics().size(); index++) {
            if (index > 0) out.append(',');
            out.append(quote(outcome.diagnostics().get(index)));
        }
        out.append("],\"operations\":[");
        for (int index = 0; index < outcome.operations().size(); index++) {
            if (index > 0) out.append(',');
            Operation operation = outcome.operations().get(index);
            FieldFact authority = operation.authority();
            out.append("{\"file\":").append(quote(operation.file()))
                    .append(",\"line\":").append(operation.line())
                    .append(",\"column\":").append(operation.column())
                    .append(",\"evidence\":").append(quote(operation.evidence()))
                    .append(",\"operation\":").append(quote(operation.operation()))
                    .append(",\"literal\":").append(quote(operation.literal()))
                    .append(",\"unsafe_reference_equality\":").append(operation.unsafeReferenceEquality())
                    .append(",\"field_owner\":").append(quote(authority.owner()))
                    .append(",\"package_name\":").append(quote(authority.packageName()))
                    .append(",\"field\":").append(quote(authority.field()))
                    .append(",\"field_type\":\"java.lang.String\"")
                    .append(",\"declaration_file\":").append(quote(authority.declarationFile()))
                    .append(",\"declaration_line\":").append(authority.declarationLine())
                    .append('}');
        }
        return out.append("]}").toString();
    }
}

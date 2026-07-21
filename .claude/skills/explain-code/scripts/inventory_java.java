// Inventory direct public Java declarations using only the JDK compiler tree API.
// This helper parses source; it does not resolve inherited, generated, or framework behavior.
import com.sun.source.doctree.DocCommentTree;
import com.sun.source.tree.BinaryTree;
import com.sun.source.tree.CatchTree;
import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.ConditionalExpressionTree;
import com.sun.source.tree.DoWhileLoopTree;
import com.sun.source.tree.EnhancedForLoopTree;
import com.sun.source.tree.ForLoopTree;
import com.sun.source.tree.IfTree;
import com.sun.source.tree.LambdaExpressionTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.SwitchExpressionTree;
import com.sun.source.tree.SwitchTree;
import com.sun.source.tree.Tree;
import com.sun.source.tree.VariableTree;
import com.sun.source.tree.WhileLoopTree;
import com.sun.source.util.DocTrees;
import com.sun.source.util.JavacTask;
import com.sun.source.util.SourcePositions;
import com.sun.source.util.TreePath;
import com.sun.source.util.TreeScanner;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import javax.lang.model.element.Modifier;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

public class inventory_java {
    private record Target(String symbol, String kind, long line, long loc, int branchCount, boolean hasDocstring) {}

    private static void fail(String message) {
        System.err.println("[inventory_java] " + message);
        System.exit(2);
    }

    public static void main(String[] args) throws Exception {
        Path file = null;
        String display = null;
        for (int index = 0; index < args.length; index++) {
            switch (args[index]) {
                case "--file" -> file = Path.of(args[++index]).toAbsolutePath().normalize();
                case "--display" -> display = args[++index];
                default -> fail("unknown argument: " + args[index]);
            }
        }
        if (file == null || display == null) fail("--file and --display are required");
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) fail("JDK compiler API is unavailable; a JRE is insufficient");
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(diagnostics, Locale.ROOT, StandardCharsets.UTF_8)) {
            Iterable<? extends JavaFileObject> inputs = manager.getJavaFileObjects(file.toFile());
            JavacTask task = (JavacTask) compiler.getTask(null, manager, diagnostics, List.of("-proc:none", "--release", "17"), null, inputs);
            List<CompilationUnitTree> units = new ArrayList<>();
            task.parse().forEach(units::add);
            for (Diagnostic<? extends JavaFileObject> diagnostic : diagnostics.getDiagnostics()) {
                if (diagnostic.getKind() == Diagnostic.Kind.ERROR) {
                    fail("syntax error in " + display + ":" + diagnostic.getLineNumber() + ": " + diagnostic.getMessage(Locale.ROOT));
                }
            }
            if (units.size() != 1) fail("expected exactly one compilation unit for " + display);
            CompilationUnitTree unit = units.get(0);
            SourcePositions positions = DocTrees.instance(task).getSourcePositions();
            DocTrees docs = DocTrees.instance(task);
            List<Target> targets = new ArrayList<>();
            int total = 0;
            for (Tree declaration : unit.getTypeDecls()) {
                if (!(declaration instanceof ClassTree owner)) continue;
                total++;
                if (!owner.getModifiers().getFlags().contains(Modifier.PUBLIC)) continue;
                String ownerName = owner.getSimpleName().toString();
                targets.add(fact(unit, positions, docs, new TreePath(new TreePath(unit), owner), ownerName, "type", owner, 0));
                boolean interfaceOwner = owner.getKind() == Tree.Kind.INTERFACE || owner.getKind() == Tree.Kind.ANNOTATION_TYPE;
                for (Tree member : owner.getMembers()) {
                    if (member instanceof MethodTree method) {
                        total++;
                        Set<Modifier> flags = method.getModifiers().getFlags();
                        if (!flags.contains(Modifier.PUBLIC) && !(interfaceOwner && !flags.contains(Modifier.PRIVATE))) continue;
                        boolean constructor = method.getName().contentEquals("<init>");
                        String symbol = ownerName + "." + (constructor ? ownerName : method.getName());
                        targets.add(fact(unit, positions, docs, TreePath.getPath(unit, method), symbol, constructor ? "constructor" : "method", method, branchCount(method)));
                    } else if (member instanceof VariableTree field) {
                        total++;
                        Set<Modifier> flags = field.getModifiers().getFlags();
                        if (!flags.contains(Modifier.PUBLIC) && !interfaceOwner) continue;
                        targets.add(fact(unit, positions, docs, TreePath.getPath(unit, field), ownerName + "." + field.getName(), "field", field, 0));
                    }
                }
            }
            System.out.println(render(targets, total));
        }
    }

    private static Target fact(CompilationUnitTree unit, SourcePositions positions, DocTrees docs, TreePath path, String symbol, String kind, Tree tree, int branches) {
        long start = positions.getStartPosition(unit, tree);
        long end = positions.getEndPosition(unit, tree);
        if (start < 0 || end < 0) fail("cannot locate declaration " + symbol);
        long line = unit.getLineMap().getLineNumber(start);
        long endLine = unit.getLineMap().getLineNumber(Math.max(start, end - 1));
        DocCommentTree comment = path == null ? null : docs.getDocCommentTree(path);
        return new Target(symbol, kind, line, Math.max(1, endLine - line + 1), branches, comment != null);
    }

    private static int branchCount(MethodTree method) {
        if (method.getBody() == null) return 0;
        BranchCounter counter = new BranchCounter();
        counter.scan(method.getBody(), null);
        return counter.score;
    }

    private static final class BranchCounter extends TreeScanner<Void, Void> {
        private int score;
        @Override public Void visitIf(IfTree node, Void unused) { score++; return super.visitIf(node, unused); }
        @Override public Void visitForLoop(ForLoopTree node, Void unused) { score++; return super.visitForLoop(node, unused); }
        @Override public Void visitEnhancedForLoop(EnhancedForLoopTree node, Void unused) { score++; return super.visitEnhancedForLoop(node, unused); }
        @Override public Void visitWhileLoop(WhileLoopTree node, Void unused) { score++; return super.visitWhileLoop(node, unused); }
        @Override public Void visitDoWhileLoop(DoWhileLoopTree node, Void unused) { score++; return super.visitDoWhileLoop(node, unused); }
        @Override public Void visitSwitch(SwitchTree node, Void unused) { score++; return super.visitSwitch(node, unused); }
        @Override public Void visitSwitchExpression(SwitchExpressionTree node, Void unused) { score++; return super.visitSwitchExpression(node, unused); }
        @Override public Void visitCatch(CatchTree node, Void unused) { score++; return super.visitCatch(node, unused); }
        @Override public Void visitConditionalExpression(ConditionalExpressionTree node, Void unused) { score++; return super.visitConditionalExpression(node, unused); }
        @Override public Void visitBinary(BinaryTree node, Void unused) {
            if (node.getKind() == Tree.Kind.CONDITIONAL_AND || node.getKind() == Tree.Kind.CONDITIONAL_OR) score++;
            return super.visitBinary(node, unused);
        }
        @Override public Void visitLambdaExpression(LambdaExpressionTree node, Void unused) { return null; }
        @Override public Void visitClass(ClassTree node, Void unused) { return null; }
    }

    private static String quote(String value) {
        StringBuilder out = new StringBuilder("\"");
        for (char character : value.toCharArray()) {
            switch (character) {
                case '\\' -> out.append("\\\\");
                case '\"' -> out.append("\\\"");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> out.append(character);
            }
        }
        return out.append('\"').toString();
    }

    private static String render(List<Target> targets, int total) {
        StringBuilder out = new StringBuilder("{\"total_symbols\":").append(total).append(",\"targets\":[");
        for (int index = 0; index < targets.size(); index++) {
            if (index > 0) out.append(',');
            Target target = targets.get(index);
            out.append("{\"symbol\":").append(quote(target.symbol()))
                    .append(",\"kind\":").append(quote(target.kind()))
                    .append(",\"lineno\":").append(target.line())
                    .append(",\"loc\":").append(target.loc())
                    .append(",\"branch_count\":").append(target.branchCount())
                    .append(",\"has_docstring\":").append(target.hasDocstring()).append('}');
        }
        return out.append("]}").toString();
    }
}

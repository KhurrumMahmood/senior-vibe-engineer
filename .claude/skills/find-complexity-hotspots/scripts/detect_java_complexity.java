// Extract syntax-only Java method complexity using the JDK compiler tree API.
//
// This helper is family-local and parse-only. It resolves no types, build
// system, framework, runtime dispatch, or performance behavior.
import com.sun.source.tree.AnnotationTree;
import com.sun.source.tree.BinaryTree;
import com.sun.source.tree.BlockTree;
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
import com.sun.source.tree.WhileLoopTree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.SourcePositions;
import com.sun.source.util.TreeScanner;
import com.sun.source.util.Trees;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Locale;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

public class detect_java_complexity {
    private record FunctionFact(
            String symbol, String kind, int branchScore, long line, long endLine, long loc) {}

    private record FileFact(String file, String status, List<FunctionFact> records, String error) {}

    private static void fail(String message) {
        System.err.println("[detect_java_complexity] " + message);
        System.exit(2);
    }

    public static void main(String[] args) throws Exception {
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
            fail("usage: detect_java_complexity.java --project-root <root> --file <source> [--file <source> ...]");
        }
        if (ToolProvider.getSystemJavaCompiler() == null) {
            fail("JDK compiler API is unavailable; a JRE is insufficient");
        }
        List<FileFact> results = new ArrayList<>();
        for (Path file : files) results.add(analyze(projectRoot, file));
        System.out.println(render(results));
    }

    private static FileFact analyze(Path projectRoot, Path file) throws IOException {
        String relative = relative(projectRoot, file);
        if (!file.startsWith(projectRoot) || !file.toString().toLowerCase(Locale.ROOT).endsWith(".java")) {
            return new FileFact(relative, "invalid-source", List.of(), "source is outside root or not .java");
        }
        String source = Files.readString(file, StandardCharsets.UTF_8);
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(diagnostics, Locale.ROOT, StandardCharsets.UTF_8)) {
            Iterable<? extends JavaFileObject> units = manager.getJavaFileObjects(file.toFile());
            JavacTask task = (JavacTask) compiler.getTask(
                    null, manager, diagnostics, List.of("-proc:none", "-Xlint:none"), null, units);
            List<CompilationUnitTree> parsed = new ArrayList<>();
            for (CompilationUnitTree unit : task.parse()) parsed.add(unit);
            List<String> errors = diagnostics.getDiagnostics().stream()
                    .filter(row -> row.getKind() == Diagnostic.Kind.ERROR)
                    .map(row -> "line " + row.getLineNumber() + ": " + row.getMessage(Locale.ROOT))
                    .toList();
            if (!errors.isEmpty() || parsed.size() != 1) {
                return new FileFact(relative, "syntax-error", List.of(), String.join("; ", errors));
            }
            CompilationUnitTree unit = parsed.get(0);
            if (isGenerated(unit, source)) {
                return new FileFact(relative, "generated", List.of(), "");
            }
            Trees trees = Trees.instance(task);
            FunctionCollector collector = new FunctionCollector(unit, trees.getSourcePositions());
            collector.scan(unit, null);
            return new FileFact(relative, "complete", collector.records, "");
        }
    }

    private static boolean isGenerated(CompilationUnitTree unit, String source) {
        String head = source.substring(0, Math.min(source.length(), 2048)).toLowerCase(Locale.ROOT);
        if (head.contains("generated by") && head.contains("do not edit")) return true;
        for (Tree declaration : unit.getTypeDecls()) {
            if (declaration instanceof ClassTree type) {
                for (AnnotationTree annotation : type.getModifiers().getAnnotations()) {
                    String name = annotation.getAnnotationType().toString();
                    if (name.equals("Generated") || name.endsWith(".Generated")) return true;
                }
            }
        }
        return false;
    }

    private static final class FunctionCollector extends TreeScanner<Void, Void> {
        private final CompilationUnitTree unit;
        private final SourcePositions positions;
        private final Deque<String> types = new ArrayDeque<>();
        private final List<FunctionFact> records = new ArrayList<>();

        private FunctionCollector(CompilationUnitTree unit, SourcePositions positions) {
            this.unit = unit;
            this.positions = positions;
        }

        @Override
        public Void visitClass(ClassTree node, Void unused) {
            String name = node.getSimpleName().toString();
            types.addLast(name.isEmpty() ? "anonymous" : name);
            super.visitClass(node, unused);
            types.removeLast();
            return null;
        }

        @Override
        public Void visitMethod(MethodTree node, Void unused) {
            BlockTree body = node.getBody();
            if (body == null) return null;
            String rawName = node.getName().toString();
            String owner = String.join(".", types);
            boolean constructor = rawName.equals("<init>");
            String displayName = constructor && !types.isEmpty() ? types.peekLast() : rawName;
            String symbol = owner.isEmpty() ? displayName : owner + "." + displayName;
            long start = positions.getStartPosition(unit, node);
            long end = positions.getEndPosition(unit, node);
            if (start < 0 || end < 0) return null;
            long line = unit.getLineMap().getLineNumber(start);
            long endLine = unit.getLineMap().getLineNumber(Math.max(start, end - 1));
            BranchCounter counter = new BranchCounter();
            counter.scan(body, null);
            records.add(new FunctionFact(
                    symbol,
                    constructor ? "constructor" : "method",
                    counter.score,
                    line,
                    endLine,
                    Math.max(1, endLine - line + 1)));
            return null;
        }
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
        @Override
        public Void visitBinary(BinaryTree node, Void unused) {
            if (node.getKind() == Tree.Kind.CONDITIONAL_AND || node.getKind() == Tree.Kind.CONDITIONAL_OR) score++;
            return super.visitBinary(node, unused);
        }
        @Override public Void visitLambdaExpression(LambdaExpressionTree node, Void unused) { return null; }
        @Override public Void visitClass(ClassTree node, Void unused) { return null; }
    }

    private static String relative(Path root, Path file) {
        try { return root.relativize(file).toString().replace('\\', '/'); }
        catch (IllegalArgumentException error) { return file.toString().replace('\\', '/'); }
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

    private static String render(List<FileFact> files) {
        StringBuilder out = new StringBuilder();
        out.append("{\"schema_version\":1,\"analyzer\":\"jdk-compiler-tree-api\",\"java_version\":")
                .append(quote(System.getProperty("java.version"))).append(",\"files\":[");
        for (int fileIndex = 0; fileIndex < files.size(); fileIndex++) {
            if (fileIndex > 0) out.append(',');
            FileFact file = files.get(fileIndex);
            out.append("{\"file\":").append(quote(file.file()))
                    .append(",\"status\":").append(quote(file.status()))
                    .append(",\"error\":").append(quote(file.error()))
                    .append(",\"records\":[");
            for (int recordIndex = 0; recordIndex < file.records().size(); recordIndex++) {
                if (recordIndex > 0) out.append(',');
                FunctionFact record = file.records().get(recordIndex);
                out.append("{\"symbol\":").append(quote(record.symbol()))
                        .append(",\"kind\":").append(quote(record.kind()))
                        .append(",\"branch_score\":").append(record.branchScore())
                        .append(",\"lineno\":").append(record.line())
                        .append(",\"end_lineno\":").append(record.endLine())
                        .append(",\"loc\":").append(record.loc()).append('}');
            }
            out.append("]}");
        }
        return out.append("]}").toString();
    }
}

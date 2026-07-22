// Extract direct Java method-invocation facts using only the public JDK tree API.
//
// This family-local helper parses syntax only. It resolves no classes, imports,
// overloads, aliases, runtime dispatch, build system, or framework behavior.
import com.sun.source.tree.AnnotationTree;
import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.ExpressionTree;
import com.sun.source.tree.IdentifierTree;
import com.sun.source.tree.LambdaExpressionTree;
import com.sun.source.tree.MemberSelectTree;
import com.sun.source.tree.MethodInvocationTree;
import com.sun.source.tree.ParenthesizedTree;
import com.sun.source.tree.Tree;
import com.sun.source.tree.TryTree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.SourcePositions;
import com.sun.source.util.TreeScanner;
import com.sun.source.util.Trees;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

public class detect_java_calls {
    private record CallFact(String name, long line, String text, boolean inTry) {}

    private record FileFact(String file, String status, List<CallFact> records, String error) {}

    private static void fail(String message) {
        System.err.println("[detect_java_calls] " + message);
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
            fail("usage: detect_java_calls.java --project-root <root> --file <source> [--file <source> ...]");
        }
        if (ToolProvider.getSystemJavaCompiler() == null) {
            fail("JDK compiler API is unavailable; a JRE is insufficient");
        }
        List<FileFact> results = new ArrayList<>();
        for (Path file : files) results.add(analyze(projectRoot, file));
        System.out.println(render(results));
    }

    private static FileFact analyze(Path projectRoot, Path file) {
        String relative = relative(projectRoot, file);
        if (!file.startsWith(projectRoot) || !file.toString().toLowerCase(Locale.ROOT).endsWith(".java")) {
            return new FileFact(relative, "read-error", List.of(), "source is outside root or not .java");
        }
        final String source;
        try {
            source = Files.readString(file, StandardCharsets.UTF_8);
        } catch (IOException error) {
            return new FileFact(relative, "read-error", List.of(), error.getMessage());
        }
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(
                diagnostics, Locale.ROOT, StandardCharsets.UTF_8)) {
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
            CallCollector collector = new CallCollector(unit, trees.getSourcePositions(), source);
            collector.scan(unit, false);
            return new FileFact(relative, "complete", collector.records, "");
        } catch (IOException error) {
            return new FileFact(relative, "read-error", List.of(), error.getMessage());
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

    private static final class CallCollector extends TreeScanner<Void, Boolean> {
        private final CompilationUnitTree unit;
        private final SourcePositions positions;
        private final String source;
        private final List<CallFact> records = new ArrayList<>();

        private CallCollector(CompilationUnitTree unit, SourcePositions positions, String source) {
            this.unit = unit;
            this.positions = positions;
            this.source = source;
        }

        @Override
        public Void visitMethodInvocation(MethodInvocationTree node, Boolean inTry) {
            String name = dotted(node.getMethodSelect());
            if (!name.isEmpty()) {
                long start = positions.getStartPosition(unit, node);
                long end = positions.getEndPosition(unit, node);
                long line = start < 0 ? 0 : unit.getLineMap().getLineNumber(start);
                records.add(new CallFact(name, line, sourceText(start, end), Boolean.TRUE.equals(inTry)));
            }
            return super.visitMethodInvocation(node, inTry);
        }

        @Override
        public Void visitTry(TryTree node, Boolean inTry) {
            for (Tree resource : node.getResources()) scan(resource, true);
            scan(node.getBlock(), true);
            for (Tree catcher : node.getCatches()) scan(catcher, inTry);
            if (node.getFinallyBlock() != null) scan(node.getFinallyBlock(), inTry);
            return null;
        }

        @Override
        public Void visitLambdaExpression(LambdaExpressionTree node, Boolean inTry) {
            scan(node.getBody(), false);
            return null;
        }

        @Override
        public Void visitClass(ClassTree node, Boolean inTry) {
            // Bodies of local/anonymous classes run on a distinct execution path.
            for (Tree member : node.getMembers()) scan(member, false);
            return null;
        }

        private String sourceText(long start, long end) {
            if (start < 0 || end < start || start >= source.length()) return "";
            int finish = (int) Math.min(end, source.length());
            return source.substring((int) start, finish).replaceAll("\\s+", " ").trim();
        }

        private static String dotted(ExpressionTree node) {
            if (node instanceof IdentifierTree identifier) return identifier.getName().toString();
            if (node instanceof MemberSelectTree select) {
                String base = dotted(select.getExpression());
                return base.isEmpty() ? "" : base + "." + select.getIdentifier();
            }
            if (node instanceof ParenthesizedTree parenthesized) return dotted(parenthesized.getExpression());
            return "";
        }
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
                CallFact record = file.records().get(recordIndex);
                out.append("{\"name\":").append(quote(record.name()))
                        .append(",\"line\":").append(record.line())
                        .append(",\"text\":").append(quote(record.text()))
                        .append(",\"in_try\":").append(record.inTry()).append('}');
            }
            out.append("]}");
        }
        return out.append("]}").toString();
    }
}

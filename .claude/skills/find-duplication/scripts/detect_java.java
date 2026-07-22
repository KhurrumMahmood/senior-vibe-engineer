// Detect exact normalized direct Java method/constructor-body clones.
import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.Tree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.SourcePositions;
import com.sun.source.util.Trees;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

public class detect_java {
    private record MethodFact(String name, long startLine, long endLine, long loc, String fingerprint) {}
    private record FileFact(String file, String status, String error, List<MethodFact> methods) {}

    private static void fail(String message) {
        System.err.println("[detect_java] " + message);
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
        if (ToolProvider.getSystemJavaCompiler() == null) fail("JDK compiler API is unavailable; a JRE is insufficient");
        List<FileFact> results = new ArrayList<>();
        for (Path file : files) results.add(analyze(projectRoot, file));
        System.out.println(render(results));
    }

    private static FileFact analyze(Path projectRoot, Path file) throws Exception {
        String relative = projectRoot.relativize(file).toString().replace('\\', '/');
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(diagnostics, Locale.ROOT, StandardCharsets.UTF_8)) {
            Iterable<? extends JavaFileObject> inputs = manager.getJavaFileObjects(file.toFile());
            JavacTask task = (JavacTask) compiler.getTask(null, manager, diagnostics, List.of("-proc:none", "--release", "17"), null, inputs);
            List<CompilationUnitTree> units = new ArrayList<>();
            task.parse().forEach(units::add);
            for (Diagnostic<? extends JavaFileObject> diagnostic : diagnostics.getDiagnostics()) {
                if (diagnostic.getKind() == Diagnostic.Kind.ERROR) {
                    return new FileFact(relative, "syntax-error", "line " + diagnostic.getLineNumber() + ": " + diagnostic.getMessage(Locale.ROOT), List.of());
                }
            }
            if (units.size() != 1) return new FileFact(relative, "invalid-result", "expected one compilation unit", List.of());
            CompilationUnitTree unit = units.get(0);
            SourcePositions positions = Trees.instance(task).getSourcePositions();
            List<MethodFact> methods = new ArrayList<>();
            for (Tree declaration : unit.getTypeDecls()) {
                if (!(declaration instanceof ClassTree owner)) continue;
                String ownerName = owner.getSimpleName().toString();
                if (ownerName.isEmpty()) continue;
                for (Tree member : owner.getMembers()) {
                    if (!(member instanceof MethodTree method) || method.getBody() == null) continue;
                    long start = positions.getStartPosition(unit, method);
                    long end = positions.getEndPosition(unit, method);
                    if (start < 0 || end < 0) continue;
                    long startLine = unit.getLineMap().getLineNumber(start);
                    long endLine = unit.getLineMap().getLineNumber(Math.max(start, end - 1));
                    long loc = Math.max(1, endLine - startLine + 1);
                    if (loc < 5) continue;
                    String methodName = method.getName().contentEquals("<init>") ? ownerName : method.getName().toString();
                    String normalized = method.getBody().toString();
                    MessageDigest digest = MessageDigest.getInstance("SHA-256");
                    String fingerprint = HexFormat.of().formatHex(digest.digest(normalized.getBytes(StandardCharsets.UTF_8)));
                    methods.add(new MethodFact(ownerName + "." + methodName, startLine, endLine, loc, fingerprint));
                }
            }
            return new FileFact(relative, "complete", "", methods);
        }
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

    private static String render(List<FileFact> files) {
        StringBuilder out = new StringBuilder("{\"schema_version\":1,\"analyzer\":\"jdk-tree-exact-method-body\",\"java_version\":")
                .append(quote(System.getProperty("java.version"))).append(",\"files\":[");
        for (int fileIndex = 0; fileIndex < files.size(); fileIndex++) {
            if (fileIndex > 0) out.append(',');
            FileFact file = files.get(fileIndex);
            out.append("{\"file\":").append(quote(file.file()))
                    .append(",\"status\":").append(quote(file.status()))
                    .append(",\"error\":").append(quote(file.error())).append(",\"methods\":[");
            for (int methodIndex = 0; methodIndex < file.methods().size(); methodIndex++) {
                if (methodIndex > 0) out.append(',');
                MethodFact method = file.methods().get(methodIndex);
                out.append("{\"name\":").append(quote(method.name()))
                        .append(",\"start_line\":").append(method.startLine())
                        .append(",\"end_line\":").append(method.endLine())
                        .append(",\"loc\":").append(method.loc())
                        .append(",\"fingerprint\":").append(quote(method.fingerprint())).append('}');
            }
            out.append("]}");
        }
        return out.append("]}").toString();
    }
}

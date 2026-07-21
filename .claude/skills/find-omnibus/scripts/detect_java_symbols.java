// Extract direct Java top-level-type method facts with only public JDK 17 APIs.
// This family-local helper parses syntax only: it resolves no imports, types,
// aliases, overloads, receivers, build files, or framework behavior.
import com.sun.source.tree.AnnotationTree;
import com.sun.source.tree.BlockTree;
import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.Tree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.SourcePositions;
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

public class detect_java_symbols {
    private record SymbolFact(
            String name, String clusterName, String kind, long line, long endLine, long loc) {}

    private record FileFact(String file, String status, List<SymbolFact> symbols, String error) {}

    private static void fail(String message) {
        System.err.println("[detect_java_symbols] " + message);
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
            fail("usage: detect_java_symbols.java --project-root <root> --file <source> [--file <source> ...]");
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
            SourcePositions positions = trees.getSourcePositions();
            List<SymbolFact> symbols = new ArrayList<>();
            for (Tree declaration : unit.getTypeDecls()) {
                if (!(declaration instanceof ClassTree type)) continue;
                String typeName = type.getSimpleName().toString();
                if (typeName.isEmpty()) continue;
                for (Tree member : type.getMembers()) {
                    if (!(member instanceof MethodTree method)) continue;
                    BlockTree body = method.getBody();
                    if (body == null) continue;
                    long start = positions.getStartPosition(unit, method);
                    long end = positions.getEndPosition(unit, method);
                    if (start < 0 || end < 0) continue;
                    boolean constructor = method.getName().contentEquals("<init>");
                    String memberName = constructor ? typeName : method.getName().toString();
                    long line = unit.getLineMap().getLineNumber(start);
                    long endLine = unit.getLineMap().getLineNumber(Math.max(start, end - 1));
                    symbols.add(new SymbolFact(
                            typeName + "." + memberName,
                            memberName,
                            constructor ? "constructor" : "method",
                            line,
                            endLine,
                            Math.max(1, endLine - line + 1)));
                }
            }
            return new FileFact(relative, "complete", symbols, "");
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
                    .append(",\"symbols\":[");
            for (int symbolIndex = 0; symbolIndex < file.symbols().size(); symbolIndex++) {
                if (symbolIndex > 0) out.append(',');
                SymbolFact symbol = file.symbols().get(symbolIndex);
                out.append("{\"name\":").append(quote(symbol.name()))
                        .append(",\"cluster_name\":").append(quote(symbol.clusterName()))
                        .append(",\"kind\":").append(quote(symbol.kind()))
                        .append(",\"lineno\":").append(symbol.line())
                        .append(",\"end_lineno\":").append(symbol.endLine())
                        .append(",\"loc\":").append(symbol.loc()).append('}');
            }
            out.append("]}");
        }
        return out.append("]}").toString();
    }
}

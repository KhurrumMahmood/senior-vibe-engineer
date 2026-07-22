// Extract real Java comment references using public JDK 17 APIs plus a small
// family-local lexer. The Compiler Tree API validates syntax; ordinary comment
// trivia is not exposed by that public API, so the lexer runs only after parse.
// It resolves no types, imports, packages, build files, or framework behavior.
import com.sun.source.tree.AnnotationTree;
import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.Tree;
import com.sun.source.util.JavacTask;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

public class detect_java_comments {
    private static final Pattern DECISION_REFERENCE = Pattern.compile("\\bdecision:(\\d{4})\\b");

    private record Reference(int line, String id, String commentForm) {}

    private record FileFact(String file, String status, List<Reference> records, String error) {}

    private record Cursor(int index, int line) {}

    private static void fail(String message) {
        System.err.println("[detect_java_comments] " + message);
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
            fail("usage: detect_java_comments.java --project-root <root> --file <source> [--file <source> ...]");
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
            return new FileFact(relative, "complete", findReferences(translateUnicodeEscapes(source)), "");
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

    // Java translates eligible Unicode escapes before tokenizing. This preserves
    // escaped delimiters for the lexer while leaving doubled backslashes literal.
    private static String translateUnicodeEscapes(String raw) {
        StringBuilder output = new StringBuilder(raw.length());
        int backslashRun = 0;
        for (int index = 0; index < raw.length();) {
            char character = raw.charAt(index);
            if (character == '\\' && backslashRun % 2 == 0) {
                int cursor = index + 1;
                while (cursor < raw.length() && raw.charAt(cursor) == 'u') cursor++;
                if (cursor > index + 1 && cursor + 4 <= raw.length()) {
                    int value = 0;
                    boolean valid = true;
                    for (int digit = 0; digit < 4; digit++) {
                        int hex = Character.digit(raw.charAt(cursor + digit), 16);
                        if (hex < 0) {
                            valid = false;
                            break;
                        }
                        value = value * 16 + hex;
                    }
                    if (valid) {
                        char translated = (char) value;
                        output.append(translated);
                        backslashRun = translated == '\\' ? backslashRun + 1 : 0;
                        index = cursor + 4;
                        continue;
                    }
                }
            }
            output.append(character);
            backslashRun = character == '\\' ? backslashRun + 1 : 0;
            index++;
        }
        return output.toString();
    }

    private static List<Reference> findReferences(String source) {
        List<Reference> references = new ArrayList<>();
        int index = 0;
        int line = 1;
        while (index < source.length()) {
            char character = source.charAt(index);
            if (character == '/' && index + 1 < source.length() && source.charAt(index + 1) == '/') {
                int start = index;
                int startLine = line;
                index += 2;
                while (index < source.length() && !isLineBreak(source.charAt(index))) index++;
                addReferences(references, source.substring(start, index), startLine, "line");
                continue;
            }
            if (character == '/' && index + 1 < source.length() && source.charAt(index + 1) == '*') {
                int start = index;
                int startLine = line;
                index += 2;
                while (index < source.length()) {
                    if (index + 1 < source.length() && source.charAt(index) == '*' && source.charAt(index + 1) == '/') {
                        index += 2;
                        break;
                    }
                    Cursor next = advance(source, index, line);
                    index = next.index();
                    line = next.line();
                }
                addReferences(references, source.substring(start, index), startLine, "block");
                continue;
            }
            if (character == '"') {
                Cursor next = startsTextBlock(source, index)
                        ? skipTextBlock(source, index, line)
                        : skipQuoted(source, index, line, '"');
                index = next.index();
                line = next.line();
                continue;
            }
            if (character == '\'') {
                Cursor next = skipQuoted(source, index, line, '\'');
                index = next.index();
                line = next.line();
                continue;
            }
            Cursor next = advance(source, index, line);
            index = next.index();
            line = next.line();
        }
        references.sort((left, right) -> {
            int lineCompare = Integer.compare(left.line(), right.line());
            return lineCompare != 0 ? lineCompare : left.id().compareTo(right.id());
        });
        return references;
    }

    private static boolean startsTextBlock(String source, int index) {
        return index + 2 < source.length()
                && source.charAt(index + 1) == '"'
                && source.charAt(index + 2) == '"';
    }

    private static Cursor skipTextBlock(String source, int index, int line) {
        index += 3;
        while (index < source.length()) {
            if (startsTextBlock(source, index) && !isEscaped(source, index)) return new Cursor(index + 3, line);
            Cursor next = advance(source, index, line);
            index = next.index();
            line = next.line();
        }
        return new Cursor(index, line);
    }

    private static Cursor skipQuoted(String source, int index, int line, char quote) {
        index++;
        while (index < source.length()) {
            char character = source.charAt(index);
            if (character == '\\') {
                Cursor escaped = advance(source, index + 1, line);
                index = escaped.index();
                line = escaped.line();
                continue;
            }
            if (character == quote) return new Cursor(index + 1, line);
            Cursor next = advance(source, index, line);
            index = next.index();
            line = next.line();
        }
        return new Cursor(index, line);
    }

    private static boolean isEscaped(String source, int index) {
        int slashes = 0;
        for (int cursor = index - 1; cursor >= 0 && source.charAt(cursor) == '\\'; cursor--) slashes++;
        return slashes % 2 == 1;
    }

    private static boolean isLineBreak(char character) {
        return character == '\n' || character == '\r';
    }

    private static Cursor advance(String source, int index, int line) {
        if (source.charAt(index) == '\r' && index + 1 < source.length() && source.charAt(index + 1) == '\n') {
            return new Cursor(index + 2, line + 1);
        }
        return new Cursor(index + 1, isLineBreak(source.charAt(index)) ? line + 1 : line);
    }

    private static void addReferences(List<Reference> references, String comment, int startLine, String form) {
        Matcher matcher = DECISION_REFERENCE.matcher(comment);
        while (matcher.find()) {
            references.add(new Reference(
                    startLine + lineBreaksBefore(comment, matcher.start()), matcher.group(1), form));
        }
    }

    private static int lineBreaksBefore(String value, int end) {
        int count = 0;
        for (int index = 0; index < end; index++) {
            if (value.charAt(index) == '\r') {
                count++;
                if (index + 1 < end && value.charAt(index + 1) == '\n') index++;
            } else if (value.charAt(index) == '\n') {
                count++;
            }
        }
        return count;
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
                Reference record = file.records().get(recordIndex);
                out.append("{\"line\":").append(record.line())
                        .append(",\"id\":").append(quote(record.id()))
                        .append(",\"comment_form\":").append(quote(record.commentForm())).append('}');
            }
            out.append("]}");
        }
        return out.append("]}").toString();
    }
}

package refs;

public final class DecisionRefs {
    private DecisionRefs() {}

    // decision:0001
    static String runtimeBoundary() {
        return "runtime";
    }

    \u002f\u002f decision:0001
    static String unicodeEscapedComment() {
        return "unicode";
    }

    /*
     * decision:0002
     */
    static String sourcePolicy() {
        return "source";
    }

    // decision:9999
    static String orphanedReference() {
        return "orphan";
    }

    static final String QUOTED = "decision:9001";
    static final String COMMENT_SHAPED = "/* decision:9002 */";
    static final String TEXT_BLOCK = """
            decision:9003
            // decision:9004
            /* decision:9005 */
            """;
    static final String DOUBLE_ESCAPED_UNICODE = "\\u002f\\u002f decision:9006";
}

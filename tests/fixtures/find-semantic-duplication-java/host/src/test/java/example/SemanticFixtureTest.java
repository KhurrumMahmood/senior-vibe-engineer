package example;

public final class SemanticFixtureTest {
    public static void main(String[] args) {
        int[] values = {1, 2, 3};
        if (SemanticConsumer.useIndex(values) != 6 || SemanticConsumer.useRange(values) != 6) {
            throw new AssertionError("fixture summaries changed");
        }
    }
}

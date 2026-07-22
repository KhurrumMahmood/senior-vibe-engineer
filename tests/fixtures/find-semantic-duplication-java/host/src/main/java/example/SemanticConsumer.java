package example;

public final class SemanticConsumer {
    public static int useIndex(int[] values) {
        return SemanticFixture.summarizeByIndex(values).total();
    }

    public static int useRange(int[] values) {
        return SemanticFixture.summarizeByRange(values).total();
    }

    private SemanticConsumer() {}
}

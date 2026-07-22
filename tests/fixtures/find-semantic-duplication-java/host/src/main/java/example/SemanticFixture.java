package example;

public final class SemanticFixture {
    public record Summary(String label, int total) {}
    public record OtherSummary(String label, int total) {}

    public static Summary summarizeByIndex(int[] values) {
        int total = 0;
        for (int index = 0; index < values.length; index++) {
            total += values[index];
        }
        return new Summary("index", total);
    }

    public static Summary summarizeByRange(int[] values) {
        int accumulated = 0;
        for (int value : values) {
            accumulated = Math.addExact(accumulated, value);
        }
        return new Summary("range", accumulated);
    }

    public static Summary wrapper(int[] values) {
        return summarizeByIndex(values);
    }

    public Summary instanceSummary(int value) {
        return new Summary("instance", value);
    }

    public static OtherSummary differentRecord(int value) {
        return new OtherSummary("other", value);
    }

    private SemanticFixture() {}
}

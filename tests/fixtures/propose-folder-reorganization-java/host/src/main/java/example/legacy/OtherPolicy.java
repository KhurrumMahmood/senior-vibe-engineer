package example.legacy;

public final class OtherPolicy {
    private OtherPolicy() {}

    public static int normalize(int amount) {
        return Math.max(0, amount);
    }

    public static String summarize(BillingSummary summary, int amount) {
        return summary.render(amount);
    }
}

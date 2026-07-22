package example.legacy;

public final class QuotePolicy {
    private QuotePolicy() {}

    public static int discount(int subtotal) {
        return subtotal > 100 ? 10 : 0;
    }
}

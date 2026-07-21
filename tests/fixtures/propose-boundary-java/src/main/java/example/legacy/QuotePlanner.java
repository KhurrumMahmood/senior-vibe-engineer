package example.legacy;

public final class QuotePlanner {
    public int preview(int subtotal) {
        return QuotePolicy.discount(subtotal);
    }
}

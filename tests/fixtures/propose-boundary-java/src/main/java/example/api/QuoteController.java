package example.api;

import example.legacy.QuotePlanner;

public final class QuoteController {
    private final QuotePlanner planner = new QuotePlanner();

    public int preview(int subtotal) {
        return planner.preview(subtotal);
    }

    public int capture(int amount) {
        return new example.legacy.SettlementLedger().capture(amount);
    }
}

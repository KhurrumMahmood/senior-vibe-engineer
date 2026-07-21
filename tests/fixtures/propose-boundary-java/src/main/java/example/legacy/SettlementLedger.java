package example.legacy;

public final class SettlementLedger {
    public int capture(int amount) {
        return SettlementPolicy.accept(amount) ? amount : 0;
    }
}

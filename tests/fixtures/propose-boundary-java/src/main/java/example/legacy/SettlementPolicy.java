package example.legacy;

public final class SettlementPolicy {
    private SettlementPolicy() {}

    public static boolean accept(int amount) {
        return amount > 0;
    }
}

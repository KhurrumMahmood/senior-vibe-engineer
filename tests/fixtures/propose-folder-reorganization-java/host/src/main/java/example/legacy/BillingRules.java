package example.legacy;

public final class BillingRules {
    private BillingRules() {}

    public static int discount(int amount) {
        return amount / 10;
    }
}

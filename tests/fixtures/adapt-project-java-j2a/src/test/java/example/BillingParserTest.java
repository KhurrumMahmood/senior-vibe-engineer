package example;

public final class BillingParserTest {
    public static void main(String[] args) {
        if (new BillingParser().parse(1) != 2) throw new AssertionError();
    }
}

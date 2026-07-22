package example.legacy;

public final class BillingParser {
    public int parse(String value) {
        return OtherPolicy.normalize(Integer.parseInt(value));
    }
}

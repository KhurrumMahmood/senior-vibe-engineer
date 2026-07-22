package example.app;

import example.legacy.*;

public final class WildcardConsumer {
    public int parse(String value) {
        return new BillingParser().parse(value);
    }
}

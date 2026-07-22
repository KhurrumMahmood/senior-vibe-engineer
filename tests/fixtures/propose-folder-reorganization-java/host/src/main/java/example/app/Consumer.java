package example.app;

import example.legacy.BillingParser;
import static example.legacy.BillingRules.discount;

public final class Consumer {
    public String run(String value) {
        int amount = new BillingParser().parse(value);
        return new example.legacy.BillingSummary().render(amount - discount(amount));
    }
}

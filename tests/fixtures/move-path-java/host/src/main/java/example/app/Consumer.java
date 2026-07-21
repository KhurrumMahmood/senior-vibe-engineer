package example.app;

import example.legacy.LegacyService;
import static example.legacy.LegacyPolicy.staticAllowed;

public final class Consumer {
    private final LegacyService service = new LegacyService();

    public int value() {
        return new example.legacy.LegacyPolicy().allowed() && staticAllowed() ? service.value() : 0;
    }
}

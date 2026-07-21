package example.app;

import example.legacy.LegacyService;

public final class Consumer {
    private final LegacyService service = new LegacyService();

    public int value() {
        return new example.legacy.LegacyPolicy().allowed() ? service.value() : 0;
    }
}

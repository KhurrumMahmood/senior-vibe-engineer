package example.app;

import example.features.Widget;

public final class Consumer {
    public Widget imported() {
        return new Widget();
    }

    public example.features.Panel fullyQualified() {
        return () -> "panel";
    }
}

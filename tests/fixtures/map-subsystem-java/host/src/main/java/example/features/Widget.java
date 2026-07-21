package example.features;

import example.shared.Labels;

public final class Widget {
    public static final String DEFAULT_NAME = "widget";

    public Widget() {
    }

    public Labels label() {
        return Labels.DEFAULT;
    }
}

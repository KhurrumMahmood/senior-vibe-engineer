package example;

/** Public fixture type. */
public class Service {
    public static final String VERSION = "1";
    private final String prefix;

    public Service(String prefix) {
        this.prefix = prefix;
    }

    public String render(String value) {
        if (value == null || value.isBlank()) {
            return prefix;
        }
        return prefix + value;
    }

    protected String protectedHelper() {
        return prefix;
    }

    private String privateHelper() {
        return prefix;
    }
}

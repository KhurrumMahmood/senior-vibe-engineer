package example.status;

public final class CanonicalStatus {
    public static final CanonicalStatus READY = new CanonicalStatus("ready");

    private final String value;

    public CanonicalStatus(String value) {
        this.value = value;
    }

    public String value() {
        return value;
    }
}

package example;

public final class VendorJobPayload {
    public String status;

    public boolean queued() {
        return "queued".equals(status);
    }
}

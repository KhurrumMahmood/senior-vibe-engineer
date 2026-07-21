package example;

public final class UnsafeJob {
    public String state;

    public boolean queued() {
        return state == "queued";
    }
}

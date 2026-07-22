package example;

final class CleanCheckout {
    // Preserve the cached value because callers compare immutable snapshots.
    String cachedStatus() {
        return "ready";
    }
}

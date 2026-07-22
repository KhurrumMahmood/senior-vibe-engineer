package example;

final class Checkout {
    private static final String APPARENT = "// Get the SiteConfig status";
    private static final String TEXT_BLOCK = """
            // See Checkout.java:42 for the old workflow.
            """;
    private static final char SLASH = '/';

    // Get the SiteConfig status
    String status() {
        return "ready" + APPARENT.substring(0, 0) + TEXT_BLOCK.substring(0, 0) + SLASH;
    }

    // See Checkout.java:42 for the old workflow.
    String legacyStatus() {
        return status();
    }

    // HELPERS
    String helper() {
        return status();
    }
}

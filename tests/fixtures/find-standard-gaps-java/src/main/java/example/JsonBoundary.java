package example;

public final class JsonBoundary {
    private JsonBoundary() {}

    static final class Json {
        static String decode(String value) {
            return value;
        }
    }

    static final class Resource implements AutoCloseable {
        Resource(String value) {}

        @Override
        public void close() {}
    }

    static String unsafe(String value) {
        return Json.decode(value);
    }

    static String safe(String value) {
        try {
            return Json.decode(value);
        } catch (RuntimeException error) {
            return value;
        }
    }

    static String resourceSetupIsInsideTry(String value) {
        try (Resource resource = new Resource(Json.decode(value))) {
            return value;
        }
    }

    static void lambdaRunsLater(String value) {
        try {
            Runnable task = () -> Json.decode(value);
            task.run();
        } catch (RuntimeException ignored) {
            // Fixture only: the standard concerns the direct JSON call.
        }
    }

    static void localAndAnonymousTypesRunLater(String value) {
        try {
            class LocalLater {
                void run() {
                    Json.decode(value);
                }
            }
            Runnable anonymousLater = new Runnable() {
                @Override
                public void run() {
                    Json.decode(value);
                }
            };
            new LocalLater().run();
            anonymousLater.run();
        } catch (RuntimeException ignored) {
            // Fixture only: the standard concerns the direct JSON call.
        }
    }

    static String catchAndFinallyAreOutside(String value) {
        try {
            return value;
        } catch (RuntimeException error) {
            return Json.decode(value);
        } finally {
            Json.decode(value);
        }
    }
}

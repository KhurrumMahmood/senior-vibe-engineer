package example.app;

public final class ReflectionLookup {
    public Class<?> load() throws ClassNotFoundException {
        return Class.forName("example.status.LegacyStatus");
    }
}

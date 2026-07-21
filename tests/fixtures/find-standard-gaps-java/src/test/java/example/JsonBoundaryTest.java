package example;

final class JsonBoundaryTest {
    static String ignored(String value) {
        return JsonBoundary.Json.decode(value);
    }
}

package example;

final class VendorBoundary {
    static String ignored(String value) {
        return JsonBoundary.Json.decode(value);
    }
}

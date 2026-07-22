package vendor.example;

public final class VendorSweep {
    public record Options(String id, String region) {
        public Options(String id) { this(id, "global"); }
    }
    public static Options one() { return new Options("one", "us"); }
    public static Options two() { return new Options("two", "us"); }
    public static Options three() { return new Options("three", "us"); }
    public static Options old() { return new Options("old"); }
}

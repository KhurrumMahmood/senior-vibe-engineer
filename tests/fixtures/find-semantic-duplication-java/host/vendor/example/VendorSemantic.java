package vendor.example;

public final class VendorSemantic {
    public record Result(String label, int total) {}
    public static Result first() { return new Result("one", 1); }
    public static Result second() { return new Result("two", 2); }
    public static int callFirst() { return first().total(); }
    public static int callSecond() { return second().total(); }
}

package example;

public final class SweepFixture {
    public record RequestOptions(String id, String region) {
        public RequestOptions(String id) {
            this(id, "global");
        }
    }

    public record StableOptions(String id, String region) {
        public StableOptions(String id) {
            this(id, "global");
        }
    }

    public static RequestOptions first() {
        return new RequestOptions("first", "us"); // swept
    }

    public static RequestOptions second() {
        return new RequestOptions("second", "us"); // swept
    }

    public static RequestOptions third() {
        return new RequestOptions("third", "us"); // swept
    }

    public static RequestOptions straggler() {
        return new RequestOptions("straggler");
    }

    public static StableOptions stableOne() {
        return new StableOptions("one", "global");
    }

    public static StableOptions stableTwo() {
        return new StableOptions("two", "global");
    }

    public static StableOptions stableThree() {
        return new StableOptions("three", "global");
    }

    public static StableOptions stableDefault() {
        return new StableOptions("default");
    }

    private SweepFixture() {}
}

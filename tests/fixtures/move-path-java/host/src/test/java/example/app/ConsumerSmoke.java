package example.app;

public final class ConsumerSmoke {
    public static void main(String[] args) {
        if (new Consumer().value() != 42) throw new AssertionError("unexpected value");
    }
}

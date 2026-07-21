package example;

public final class SweepFixtureTest {
    public static void main(String[] args) {
        if (!SweepFixture.first().region().equals("us")) {
            throw new AssertionError("explicit region changed");
        }
        if (!SweepFixture.straggler().region().equals("global")) {
            throw new AssertionError("record overload default changed");
        }
    }
}

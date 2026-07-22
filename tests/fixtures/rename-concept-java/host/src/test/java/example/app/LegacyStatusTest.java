package example.app;

import example.status.LegacyStatus;

public final class LegacyStatusTest {
    public static void main(String[] args) {
        assert new LegacyStatus("legacy").value().equals("legacy");
    }
}

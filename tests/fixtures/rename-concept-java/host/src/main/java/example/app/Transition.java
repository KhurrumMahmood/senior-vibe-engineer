package example.app;

import example.status.CanonicalStatus;
import example.status.LegacyStatus;

@NamedType("LegacyStatus")
public final class Transition {
    public CanonicalStatus convert(LegacyStatus input) {
        String LegacyStatus = input.value();
        return new CanonicalStatus(LegacyStatus);
    }
}

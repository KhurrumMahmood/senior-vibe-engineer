pub struct LegacyStatus;
pub struct CanonicalStatus;

pub fn migrate(_status: LegacyStatus) -> CanonicalStatus {
    CanonicalStatus
}

pub const REFLECTION_NAME: &str = "LegacyStatus";

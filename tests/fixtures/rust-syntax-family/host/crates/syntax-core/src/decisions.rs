// decision:0001 keeps the invoice boundary explicit.
pub fn anchored_decision() -> u8 {
    1
}

/* decision:9999 is deliberately orphaned. */
pub fn orphaned_decision() -> u8 {
    2
}

pub const COMMENT_SHAPED_STRING: &str = "// decision:7777";
pub const COMMENT_SHAPED_RAW: &str = r#"/* decision:8888 */"#;

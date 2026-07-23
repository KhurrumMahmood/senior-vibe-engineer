pub fn validate_invoice(amount: u32) -> &'static str {
    if amount > 0 { "valid" } else { "invalid" }
}

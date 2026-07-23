pub mod billing_parser;
pub mod billing_rules;
pub mod billing_summary;
pub mod cohesive;
pub mod legacy;

pub fn fixture_smoke() -> String {
    format!(
        "{}:{}:{}",
        legacy::quote::quote_total(40),
        billing_rules::validate_invoice(2),
        billing_summary::summarize_invoice(billing_parser::parse_invoice(40)),
    )
}

use super::build_statement;

pub fn statement_total(value: i32) -> i32 {
    let summary = build_statement(value);
    summary.subtotal + summary.tax
}

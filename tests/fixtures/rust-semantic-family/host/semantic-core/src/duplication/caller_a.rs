use super::summarize_invoice;

pub fn invoice_total(value: i32) -> i32 {
    let summary = summarize_invoice(value);
    summary.subtotal + summary.tax
}

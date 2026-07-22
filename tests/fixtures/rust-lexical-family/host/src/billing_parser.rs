use crate::Invoice;

pub fn normalize_invoice(identifier: &str, amount_cents: u64) -> Invoice {
    Invoice {
        identifier: identifier.trim().to_owned(),
        amount_cents,
    }
}

pub fn pending_invoice_total(values: &[u64]) -> u64 {
    let mut total = 0;
    for value in values {
        total += *value;
    }
    total
}

pub fn cancelled_order() -> &'static str {
    "cancelled"
}

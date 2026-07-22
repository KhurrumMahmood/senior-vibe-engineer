pub fn queued_invoice_total(values: &[u64]) -> u64 {
    let mut total = 0;
    for value in values {
        total += *value;
    }
    total
}

pub fn behaviorally_different(values: &[u64]) -> u64 {
    values.iter().map(|value| value * 2).sum()
}

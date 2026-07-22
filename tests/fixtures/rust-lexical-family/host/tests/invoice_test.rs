use rust_lexical_family::billing_parser::normalize_invoice;

#[test]
fn normalizes_identifier() {
    let invoice = normalize_invoice(" INV-7 ", 125);
    assert_eq!(invoice.identifier, "INV-7");
    assert_eq!(invoice.amount_cents, 125);
}

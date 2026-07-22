use billing_core::invoice::InvoiceService;

#[test]
fn renders_a_fixed_fee() {
    assert_eq!(
        InvoiceService.render("INV-42", 50_000),
        "invoice:INV-42:125"
    );
}

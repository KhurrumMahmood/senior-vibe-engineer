use billing_core::invoice::InvoiceService;

#[test]
fn totals_invoice_lines() {
    assert_eq!(InvoiceService.total_cents(&[1200, 3400]), 4600);
}

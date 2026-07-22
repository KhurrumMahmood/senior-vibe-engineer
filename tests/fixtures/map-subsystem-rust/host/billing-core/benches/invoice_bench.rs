use billing_core::invoice::InvoiceService;

fn main() {
    assert_eq!(InvoiceService.total_cents(&[1200, 3400]), 4600);
}

use billing_core::invoice::InvoiceService;
use billing_core::invoice::service::InvoiceService as DirectInvoiceService;

#[test]
fn public_reexport_and_direct_module_path_work() {
    assert_eq!(
        InvoiceService.render("INV-42", 50_000),
        "invoice:INV-42:125"
    );
    assert_eq!(DirectInvoiceService.fee_cents(99), 125);
}

use billing_core::invoice::InvoiceService;

#[test]
fn representative_bench_workload() {
    assert_eq!(InvoiceService.fee_cents(99_999), 125);
}

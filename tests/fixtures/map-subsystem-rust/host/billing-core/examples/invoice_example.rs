use billing_core::invoice::InvoiceService;

fn main() {
    println!("{}", InvoiceService.total_cents(&[1200, 3400]));
}

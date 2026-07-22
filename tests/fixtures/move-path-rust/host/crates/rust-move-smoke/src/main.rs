use billing_core::invoice::InvoiceService;

fn main() {
    println!("{}", InvoiceService.render("SMOKE-1", 50_000));
}

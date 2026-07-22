use billing_core::invoice::InvoiceService;

fn main() {
    println!("{}", InvoiceService.render("EXAMPLE", 10_000));
}

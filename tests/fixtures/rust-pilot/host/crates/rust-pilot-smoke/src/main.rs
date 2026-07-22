use billing_core::invoice::InvoiceService;

fn main() {
    println!("{}", InvoiceService.render("INV-42", 50_000));
}

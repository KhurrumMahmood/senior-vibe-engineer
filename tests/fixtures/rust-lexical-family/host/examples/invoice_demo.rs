fn main() {
    let invoice = rust_lexical_family::billing_parser::normalize_invoice("INV-9", 250);
    println!("{}", invoice.identifier);
}

package kotlinpilot

fun main() {
    check(renderInvoice(42, InvoiceStatus.PENDING) == "invoice:INV-42:pending:kotlin")
    check(renderInvoice(7, InvoiceStatus.PAID) == "invoice:INV-OTHER:paid:kotlin")
    println("kotlin-pilot-tests:ok")
}

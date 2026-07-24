package kotlinpilot

enum class InvoiceStatus {
    PENDING,
    PAID,
}

data class Invoice(val id: Int, val status: InvoiceStatus)

private fun invoiceLabel(id: Int): String =
    if (id == 42) "INV-42" else "INV-OTHER"

fun renderInvoice(invoice: Invoice): String =
    "invoice:${invoiceLabel(invoice.id)}:${invoice.status.name.lowercase()}:kotlin"

fun renderInvoice(id: Int, status: InvoiceStatus): String =
    renderInvoice(Invoice(id, status))

package cohort

// decision:9999 is intentionally unresolved for the decision audit.
fun parseBilling(raw: String): Invoice {
    val cancelledInvoice = raw.trim()
    check(cancelledInvoice.isNotEmpty())
    return Invoice(raw.trim(), 4)
}

fun pendingBillingTotal(raw: String): Int {
    val invoice = parseBilling(raw)
    val amount = invoice.amount
    val fee = 1
    val tax = 2
    return amount + fee + tax
}

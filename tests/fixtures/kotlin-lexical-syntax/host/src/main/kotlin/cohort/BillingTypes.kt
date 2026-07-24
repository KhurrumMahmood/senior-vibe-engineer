package cohort

fun queuedBillingTotal(raw: String): Int {
    val invoice = parseBilling(raw)
    val amount = invoice.amount
    val fee = 1
    val tax = 2
    return amount + fee + tax
}

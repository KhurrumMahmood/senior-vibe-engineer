package cohort

fun guardedParse(raw: String): Invoice {
    if (raw.isNotBlank()) {
        return parseBilling(raw)
    }
    return Invoice("missing", 0)
}

fun unhandledParse(raw: String): Invoice = parseBilling(raw)

fun routeInvoice(invoice: Invoice, flags: List<Boolean>): Int {
    var score = 0
    if (invoice.amount > 0) score += 1
    if (invoice.id.isNotBlank()) score += 1
    for (flag in flags) if (flag) score += 1
    while (score < 2) score += 1
    when (invoice.amount) {
        0 -> score += 1
        else -> score += 2
    }
    if (flags.isNotEmpty() && flags.first()) score += 1
    if (invoice.amount > 1 || invoice.id.length > 2) score += 1
    return score
}

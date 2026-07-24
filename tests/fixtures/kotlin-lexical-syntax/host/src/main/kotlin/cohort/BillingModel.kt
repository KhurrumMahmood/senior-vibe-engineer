package cohort

// decision:0001 keeps the source-only Kotlin boundary explicit.
data class Invoice(val id: String, val amount: Int)

sealed interface BillingOutcome {
    data class Accepted(val invoice: Invoice) : BillingOutcome
    data class Rejected(val reason: String) : BillingOutcome
}

fun Invoice.label(): String = "$id:$amount"

fun total(invoice: Invoice): Int = invoice.amount

fun total(invoices: List<Invoice>): Int = invoices.sumOf { it.amount }

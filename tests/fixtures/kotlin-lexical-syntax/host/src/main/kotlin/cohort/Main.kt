package cohort

fun main() {
    val invoice = parseBilling("queued")
    val amount = total(listOf(invoice, Invoice("extra", 8)))
    println("kotlin-lexical:$amount:${invoice.id}")
}

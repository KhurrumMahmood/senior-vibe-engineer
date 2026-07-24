package cohort

fun main() {
    check(parseBilling("queued").id == "queued")
    check(total(listOf(Invoice("a", 5), Invoice("b", 7))) == 12)
    println("kotlin-lexical-tests:ok")
}

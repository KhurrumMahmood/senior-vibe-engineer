package kotlinsemantic

fun main() {
    val job = Job()
    println("${useAlpha(7)}:${useBeta(8)}:${job.phase.wireValue}")
}

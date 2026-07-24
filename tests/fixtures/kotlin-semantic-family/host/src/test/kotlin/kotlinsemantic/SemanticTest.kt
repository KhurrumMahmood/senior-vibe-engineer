package kotlinsemantic

fun main() {
    check(useHelper(4) == 8)
    check(presentSweepA().audit)
    check(!presentSweepB().audit)
    check(!sweepStraggler().audit)
    check(useOverloads() == Pair("int:1", "string:x"))
    val job = Job()
    job.start()
    job.finish()
    check(job.phase == "done")
    check("VALUE".semanticTag() == "value")
    check(ChildHook().hook() == "child")
    println("kotlin-semantic-native-test:ok")
}

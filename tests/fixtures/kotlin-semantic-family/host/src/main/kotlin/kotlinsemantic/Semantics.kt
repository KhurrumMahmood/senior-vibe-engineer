package kotlinsemantic

class Job {
    var phase: String = "queued"

    fun start() {
        phase = "running"
    }

    fun finish() {
        phase = "done"
    }
}

private fun unusedHelper(value: Int): Int = value + 1

private fun usedHelper(value: Int): Int = value * 2

fun useHelper(value: Int): Int = usedHelper(value)

data class SweepOptions(val label: String, val audit: Boolean = false)

fun presentSweepA(): SweepOptions = SweepOptions("a", audit = true)

fun presentSweepB(): SweepOptions = SweepOptions("b", audit = false)

fun sweepStraggler(): SweepOptions = SweepOptions("legacy")

fun summarizeAlpha(amount: Int): String {
    return "receipt:$amount"
}

fun summarizeBeta(amount: Int): String {
    return "receipt:$amount"
}

fun useAlpha(amount: Int): String = summarizeAlpha(amount)

fun useBeta(amount: Int): String = summarizeBeta(amount)

fun overloaded(value: Int): String = "int:$value"

fun overloaded(value: String): String = "string:$value"

fun useOverloads(): Pair<String, String> = Pair(overloaded(1), overloaded("x"))

open class BaseHook {
    open fun hook(): String = "base"
}

class ChildHook : BaseHook() {
    override fun hook(): String = "child"
}

fun String.semanticTag(): String = lowercase()

class LegacyStatus

class CanonicalStatus

fun transition(old: LegacyStatus, new: CanonicalStatus): Pair<LegacyStatus, CanonicalStatus> =
    Pair(old, new)

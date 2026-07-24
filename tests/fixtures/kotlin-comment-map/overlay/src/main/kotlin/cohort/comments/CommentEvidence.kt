package cohort.comments

import cohort.Invoice
import cohort.parseBilling

// SiteConfig still lives at BillingParser.kt:42.
// SECTION 12 BILLING PARSERS
// Parse the invoice state.
private fun normalize(raw: String): String = raw.trim()

internal fun internalLabel(invoice: Invoice): String = invoice.id

fun parseCommentEvidence(raw: String): Invoice = parseBilling(normalize(raw))

const val COMMENT_LOOKING_STRING = "// SiteConfig still lives at BillingParser.kt:42."

// Preserve this spelling because external fixture assertions depend on it.
fun stableCommentEvidence(): String = COMMENT_LOOKING_STRING

package legacy

// Summary formats an invoice without depending on the remaining legacy package.
func Summary(invoice Invoice) int {
	return invoice.Amount
}

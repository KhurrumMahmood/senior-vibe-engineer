package legacy

// ValidAmount reports whether an invoice amount is usable.
func ValidAmount(amount int) bool {
	return amount > 0
}

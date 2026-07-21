package legacy

// Invoice is the billing input carried into the proposed package.
type Invoice struct {
	Amount int
}

// ParseInvoice normalizes one invoice amount.
func ParseInvoice(amount int) Invoice {
	return Invoice{Amount: amount}
}

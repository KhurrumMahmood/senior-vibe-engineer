package legacy

func SettlementCapture(input Input) int {
	return quoteNormalize(input.Subtotal)
}

func SettlementReceipt(input Input) string {
	return "settlement"
}

func settlementValidate(input Input) bool {
	return input.Discount >= 0
}

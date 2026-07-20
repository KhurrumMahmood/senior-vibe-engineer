package legacy

type Input struct {
	Subtotal int
	Discount int
}

func QuotePrice(input Input) int {
	return quoteNormalize(input.Subtotal) - input.Discount
}

func QuotePreview(input Input) string {
	return "quote"
}

func quoteNormalize(value int) int {
	if value < 0 {
		return 0
	}
	return value
}

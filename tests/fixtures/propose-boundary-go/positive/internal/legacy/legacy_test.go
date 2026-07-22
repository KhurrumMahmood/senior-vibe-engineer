package legacy

import "testing"

func TestQuotePrice(t *testing.T) {
	if QuotePrice(Input{Subtotal: 7, Discount: 2}) != 5 {
		t.Fatal("quote contract changed")
	}
}

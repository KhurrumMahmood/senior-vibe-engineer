package legacy

import "testing"

func TestParseInvoice(t *testing.T) {
	if got := ParseInvoice(4).Amount; got != 4 {
		t.Fatalf("ParseInvoice() amount = %d", got)
	}
}

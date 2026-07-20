package billing

import "testing"

func TestBilling(t *testing.T) {
	if !validate(parse()) {
		t.Fatal("parsed value is invalid")
	}
}

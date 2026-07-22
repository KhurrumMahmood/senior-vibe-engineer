package naming

import "testing"

func TestName(t *testing.T) {
	if got := Name(); got != "internal" {
		t.Fatalf("Name() = %q", got)
	}
}

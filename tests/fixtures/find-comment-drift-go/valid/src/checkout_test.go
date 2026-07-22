package checkout

import "testing"

// Get the SiteConfig status
func TestStatus(t *testing.T) {
	if got := status(); got != "ready" {
		t.Fatalf("status() = %q", got)
	}
}

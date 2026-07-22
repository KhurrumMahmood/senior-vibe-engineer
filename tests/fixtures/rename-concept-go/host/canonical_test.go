package renamefixture

import "testing"

func TestCanonicalStatus(t *testing.T) {
	if CanonicalStatusReady != "ready" {
		t.Fatal("unexpected status")
	}
}

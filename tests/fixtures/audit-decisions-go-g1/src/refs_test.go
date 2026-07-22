package refs

import "testing"

// decision:9004
func TestRuntimeBoundary(t *testing.T) {
	if RuntimeBoundary() != "runtime" {
		t.Fatal("unexpected runtime boundary")
	}
}

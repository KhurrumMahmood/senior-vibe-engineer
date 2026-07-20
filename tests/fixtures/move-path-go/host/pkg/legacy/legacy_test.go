package legacy_test

import (
	"testing"

	legacy "example.com/movefixture/pkg/legacy"
)

func TestValue(t *testing.T) {
	if legacy.Value != "stable" {
		t.Fatalf("unexpected value: %s", legacy.Value)
	}
}

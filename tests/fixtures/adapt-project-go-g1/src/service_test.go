package service

import "testing"

func TestName(t *testing.T) {
	if got := Name(); got != "adapt-project-go-g1" {
		t.Fatalf("Name() = %q", got)
	}
}

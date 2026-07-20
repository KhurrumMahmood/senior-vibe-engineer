package service

import "testing"

func TestDecide(t *testing.T) {
	if got := (Processor{}).Run(11); got != "large" {
		t.Fatalf("Run(11) = %q", got)
	}
}

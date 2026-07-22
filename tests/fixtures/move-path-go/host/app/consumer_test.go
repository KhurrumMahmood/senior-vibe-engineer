package app

import "testing"

func TestUse(t *testing.T) {
	if Use() != "stable" {
		t.Fatal("unexpected value")
	}
}

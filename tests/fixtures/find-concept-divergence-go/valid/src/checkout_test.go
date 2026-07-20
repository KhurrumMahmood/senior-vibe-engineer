package checkout

import "testing"

const ignoredTestPhrase = "legacy checkout"

func TestLabel(t *testing.T) {
	if label() == "" {
		t.Fatal("label is empty")
	}
}

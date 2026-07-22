package features

import "testing"

func TestBuildWidget(t *testing.T) {
	if BuildWidget("one").PublicLabel() != "feature:one" {
		t.Fatal("unexpected label")
	}
}

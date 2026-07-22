package duplicate

import "testing"

func TestSummarizeQueued(t *testing.T) {
	if got := SummarizeQueued([]string{"", "ready"}); len(got) != 1 {
		t.Fatalf("unexpected result: %v", got)
	}
}

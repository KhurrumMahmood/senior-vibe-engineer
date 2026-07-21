package semanticfixture

import "testing"

func TestSummariesAgree(t *testing.T) {
	values := []int{2, 3}
	left := SummarizeByRange(values)
	right := SummarizeByIndex(values)
	if left.Total != right.Total || len(left.Labels) != len(right.Labels) {
		t.Fatalf("summaries differ: %#v %#v", left, right)
	}
}

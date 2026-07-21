package sweepfixture

import "testing"

func TestFixtureBuildRequest(t *testing.T) {
	if got := BuildRequest("fixture", RequestOptions{ID: "fixture", Region: "us", Stage: "live"}); got != "fixture:us:live" {
		t.Fatalf("BuildRequest() = %q", got)
	}
}

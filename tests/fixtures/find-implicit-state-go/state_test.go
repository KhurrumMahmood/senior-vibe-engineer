package implicitstate

import "testing"

func TestJobState(t *testing.T) {
	job := &Job{State: "queued"}
	if !isQueued(job) {
		t.Fatal("expected queued job")
	}
}

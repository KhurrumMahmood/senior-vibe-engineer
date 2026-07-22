package complexity

import "testing"

func testOnlyHotspot(value int) int {
	if value > 0 {
		value--
	}
	if value > 1 {
		value--
	}
	if value > 2 {
		value--
	}
	if value > 3 {
		value--
	}
	if value > 4 {
		value--
	}
	if value > 5 {
		value--
	}
	if value > 6 {
		value--
	}
	if value > 7 {
		value--
	}
	if value > 8 {
		value--
	}
	if value > 9 {
		value--
	}
	if value > 10 {
		value--
	}
	if value > 11 {
		value--
	}
	if value > 12 {
		value--
	}
	if value > 13 {
		value--
	}
	if value > 14 {
		value--
	}
	if value > 15 {
		value--
	}
	if value > 16 {
		value--
	}
	if value > 17 {
		value--
	}
	return value
}

func TestHotspotFixturesCompile(t *testing.T) {
	if got := declaredHotspot(100); got != 82 {
		t.Fatalf("declaredHotspot() = %d", got)
	}
	if got := (&ComplexityService{}).methodHotspot(100); got != 82 {
		t.Fatalf("methodHotspot() = %d", got)
	}
	if got := testOnlyHotspot(100); got != 82 {
		t.Fatalf("testOnlyHotspot() = %d", got)
	}
}

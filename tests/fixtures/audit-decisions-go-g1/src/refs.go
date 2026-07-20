package refs

// decision:0001
func RuntimeBoundary() string {
	return "runtime"
}

/* decision:0002 */
func SourcePolicy() string {
	return "source"
}

// decision:9999
func OrphanedReference() string {
	return "orphan"
}

var quoted = "decision:9001"
var raw = `decision:9002`

// Decision:9003 is uppercase and unsupported.
// decision:12345 is five digits and unsupported.
var _, _ = quoted, raw

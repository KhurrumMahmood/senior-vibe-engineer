package checkout

const apparentComment = "// Get the SiteConfig status"

const rawApparentComment = `// See checkout.go:42`

// Get the SiteConfig status
func status() string {
	return "ready"
}

// See checkout.go:42 for the old workflow.
func legacyStatus() string {
	return status()
}

// HELPERS
func helper() string {
	return status()
}

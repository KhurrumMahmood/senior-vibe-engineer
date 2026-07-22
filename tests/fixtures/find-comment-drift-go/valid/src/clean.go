package checkout

// cachedStatus keeps the previous value because callers compare snapshots.
func cachedStatus() string {
	return status()
}

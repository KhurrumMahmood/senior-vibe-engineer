package duplicate

func SummarizeQueued(entries []string) []string {
	result := make([]string, 0, len(entries))
	for _, entry := range entries {
		if entry != "" {
			result = append(result, entry)
		}
	}
	return result
}

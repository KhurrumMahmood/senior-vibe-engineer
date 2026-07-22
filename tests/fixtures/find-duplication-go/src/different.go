package duplicate

func Reverse(entries []string) []string {
	result := make([]string, len(entries))
	for index, entry := range entries {
		result[len(entries)-index-1] = entry
	}
	return result
}

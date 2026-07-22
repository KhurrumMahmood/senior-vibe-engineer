//go:build specialfixture

package duplicate

func SpecialOnly(entries []string) []string {
	result := make([]string, 0, len(entries))
	for _, entry := range entries {
		result = append(result, entry)
	}
	return result
}

package semanticfixture

type Summary struct {
	Labels []string
	Total  int
}

func SummarizeByRange(values []int) Summary {
	labels := make([]string, 0, len(values))
	total := 0
	for index, value := range values {
		labels = append(labels, string(rune('a'+index)))
		total += value
	}
	return Summary{Labels: labels, Total: total}
}

func SummarizeByIndex(values []int) Summary {
	result := Summary{Labels: []string{}, Total: 0}
	for index := 0; index < len(values); index++ {
		result.Total = result.Total + values[index]
		result.Labels = append(result.Labels, string(rune('a'+index)))
	}
	return Summary{Total: result.Total, Labels: result.Labels}
}

type WrappedSummary struct {
	Labels []string
	Total  int
}

func BuildWrappedCore(values []int) WrappedSummary {
	return WrappedSummary{Labels: []string{"core"}, Total: len(values)}
}

func BuildWrappedViaCore(values []int) WrappedSummary {
	core := BuildWrappedCore(values)
	return WrappedSummary{Labels: core.Labels, Total: core.Total}
}

type CloneSummary struct {
	Labels []string
	Total  int
}

func BuildCloneOne(values []int) CloneSummary {
	return CloneSummary{Labels: []string{"clone"}, Total: len(values)}
}

func BuildCloneTwo(values []int) CloneSummary {
	return CloneSummary{Labels: []string{"clone"}, Total: len(values)}
}

type PolicySummary struct {
	Labels []string
	Total  int
}

func BuildPolicyPlain(values []int) PolicySummary {
	return PolicySummary{Labels: []string{"plain"}, Total: len(values)}
}

func BuildPolicyPanicking(values []int) PolicySummary {
	if len(values) == 0 {
		panic("empty")
	}
	return PolicySummary{Labels: []string{"non-empty"}, Total: values[0]}
}

type DynamicSummary struct {
	Labels []string
	Total  int
}

func BuildDynamicOne(values []int, apply func(int) int) DynamicSummary {
	total := 0
	for _, value := range values {
		total += apply(value)
	}
	return DynamicSummary{Labels: []string{"dynamic-one"}, Total: total}
}

func BuildDynamicTwo(values []int, apply func(int) int) DynamicSummary {
	result := 0
	for index := range values {
		result = result + apply(values[index])
	}
	return DynamicSummary{Labels: []string{"dynamic-two"}, Total: result}
}

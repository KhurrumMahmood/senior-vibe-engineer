package shipping

func ShippingQuote(weight int) int {
	return shippingNormalize(weight) * 3
}

func ShippingSchedule(weight int) string {
	if ShippingQuote(weight) > 0 {
		return "scheduled"
	}
	return "rejected"
}

func shippingNormalize(weight int) int {
	if weight < 0 {
		return 0
	}
	return weight
}

package complexity

func nestedFunctionContainer(value int) int {
	callback := func(number int) int {
		if number > 0 {
			number--
		}
		if number > 1 {
			number--
		}
		if number > 2 {
			number--
		}
		if number > 3 {
			number--
		}
		if number > 4 {
			number--
		}
		if number > 5 {
			number--
		}
		if number > 6 {
			number--
		}
		if number > 7 {
			number--
		}
		if number > 8 {
			number--
		}
		if number > 9 {
			number--
		}
		if number > 10 {
			number--
		}
		if number > 11 {
			number--
		}
		if number > 12 {
			number--
		}
		if number > 13 {
			number--
		}
		if number > 14 {
			number--
		}
		if number > 15 {
			number--
		}
		if number > 16 {
			number--
		}
		if number > 17 {
			number--
		}
		return number
	}
	return callback(value)
}

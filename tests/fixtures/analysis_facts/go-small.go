package sample

import "example/helpers"

type Runner struct{}

func convert(input int) int {
    value := helpers.ConvertValue(input)
    return value
}

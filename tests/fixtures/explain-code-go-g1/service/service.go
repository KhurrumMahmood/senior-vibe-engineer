package service

// Processor applies the locked fixture's decision rule.
type Processor struct{}

// Version identifies the fixture contract.
const Version = "v1"

// Ready reports whether the fixture is available.
var Ready = true

// Decide selects a stable label for the input.
func Decide(value int) string {
	if value > 10 {
		return "large"
	}
	return "small"
}

func hidden() string {
	return "private"
}

// Run applies Decide through a Processor.
func (Processor) Run(value int) string {
	return Decide(value)
}

func (*Processor) reset() {}

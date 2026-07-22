package sweepfixture

type RequestOptions struct {
	ID     string
	Region string
	Stage  string
}

func BuildRequest(id string, options RequestOptions) string {
	return id + ":" + options.Region + ":" + options.Stage
}

func InconsistentRequest(id string, options RequestOptions) string {
	return id + ":" + options.Region
}

func AmbiguousRequest(id string, options RequestOptions) string {
	return id + ":" + options.Region
}

type Receiver struct{}

func (Receiver) BuildRequest(id string, options RequestOptions) string {
	return id + ":" + options.Region
}

var first = BuildRequest("first", RequestOptions{ID: "first", Region: "us", Stage: "live"}) // swept
var second = BuildRequest("second", RequestOptions{ID: "second", Region: "us", Stage: "live"}) // swept
var third = BuildRequest("third", RequestOptions{ID: "third", Region: "us", Stage: "live"}) // swept
var forgotten = BuildRequest("forgotten", RequestOptions{ID: "forgotten", Stage: "live"})

var inconsistentFirst = InconsistentRequest("one", RequestOptions{ID: "one", Region: "us"})
var inconsistentSecond = InconsistentRequest("two", RequestOptions{ID: "two", Region: "eu"})
var inconsistentThird = InconsistentRequest("three", RequestOptions{ID: "three", Region: "us"})
var inconsistentMissing = InconsistentRequest("four", RequestOptions{ID: "four"})

var ambiguousOne = AmbiguousRequest("one", RequestOptions{ID: "one", Region: "us"})
var ambiguousTwo = AmbiguousRequest("two", RequestOptions{ID: "two", Region: "us"})
var ambiguousThree = AmbiguousRequest("three", RequestOptions{ID: "three", Region: "us"})
var ambiguousFour = AmbiguousRequest("four", RequestOptions{ID: "four", Region: "us"})
var ambiguousFive = AmbiguousRequest("five", RequestOptions{ID: "five", Region: "us"})
var ambiguousSix = AmbiguousRequest("six", RequestOptions{ID: "six", Region: "us"})
var ambiguousSeven = AmbiguousRequest("seven", RequestOptions{ID: "seven", Region: "us"})
var ambiguousEight = AmbiguousRequest("eight", RequestOptions{ID: "eight"})
var ambiguousNine = AmbiguousRequest("nine", RequestOptions{ID: "nine"})

var receiver = Receiver{}
var methodOne = receiver.BuildRequest("one", RequestOptions{ID: "one", Region: "us"})
var methodTwo = receiver.BuildRequest("two", RequestOptions{ID: "two", Region: "us"})
var methodThree = receiver.BuildRequest("three", RequestOptions{ID: "three", Region: "us"})
var methodMissing = receiver.BuildRequest("four", RequestOptions{ID: "four"})

var buildValue = BuildRequest
var functionValue = buildValue("value", RequestOptions{ID: "value", Region: "us"})

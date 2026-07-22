package dormant

import (
	"net/http"
	"reflect"
)

func unusedPrivate() int {
	return 1
}

func directlyUsed() int {
	return 2
}

var unusedCallback = func() int {
	return 3
}

var usedCallback = func() int {
	return 4
}

var dynamicByName = func() int {
	return 5
}

const dynamicRegistrationName = "dynamicByName"

type unusedType struct{}

type worker struct{}

func (worker) unusedMethod() {}

func PublicAPI() {}

func registeredHandler(http.ResponseWriter, *http.Request) {}

func KeepStaticReferences() {
	_ = directlyUsed()
	_ = usedCallback
	http.HandleFunc("/registered", registeredHandler)
	_ = reflect.TypeOf(0)
}

package resources

func cleanup() int { return 0 }

func consume(int) {}

func singleCleanup[T any]() {}

func pairCleanup[T, U any]() {}

func unsafeCleanup() {
	cleanup()
}

func safeCleanup() {
	defer cleanup()
}

func unsafeDeferredArgument() {
	defer consume(cleanup())
}

func genericAndParenthesizedCalls() {
	singleCleanup[int]()
	pairCleanup[int, string]()
	(cleanup)()
	defer singleCleanup[int]()
	defer pairCleanup[int, string]()
	defer (cleanup)()
}

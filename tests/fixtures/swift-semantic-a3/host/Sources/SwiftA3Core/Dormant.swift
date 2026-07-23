private func dormantDiscount(_ value: Int) -> Int {
  value + 7
}

private func reflectedHelper(_ value: Int) -> Int {
  value + 11
}

private func usedHelper(_ value: Int) -> Int {
  value * 2
}

public func activeTotal(_ value: Int) -> Int {
  usedHelper(value)
}

public let dormantReflectionDecoy = "reflectedHelper"

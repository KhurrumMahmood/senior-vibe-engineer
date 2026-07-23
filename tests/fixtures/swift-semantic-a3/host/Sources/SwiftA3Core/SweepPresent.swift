public func auditedChargePathA() -> Int {
  charge("a", audit: true)
}

public func auditedChargePathB() -> Int {
  charge("bb", audit: true)
}

public func auditedChargePathC() -> Int {
  charge("ccc", audit: true)
}

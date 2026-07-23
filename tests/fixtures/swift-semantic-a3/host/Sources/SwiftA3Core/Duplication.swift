public struct Statement {
  public let total: Int
  public let label: String

  public init(total: Int, label: String) {
    self.total = total
    self.label = label
  }
}

private func normalize(_ value: Int) -> Int {
  value * 2
}

private func policyFee(_ value: Int) -> Int {
  value + 1
}

public func buildStatement(_ value: Int) -> Statement {
  let normalized = normalize(value)
  return Statement(total: normalized, label: "invoice")
}

public func summarizeInvoice(_ value: Int) -> Statement {
  let subtotal = normalize(value)
  let category = "invoice"
  return Statement(total: subtotal, label: category)
}

public func cloneOne(_ value: Int) -> Statement {
  let normalized = normalize(value)
  return Statement(total: normalized, label: "clone")
}

public func cloneTwo(_ value: Int) -> Statement {
  let normalized = normalize(value)
  return Statement(total: normalized, label: "clone")
}

public func wrapperDecoy(_ value: Int) -> Statement {
  buildStatement(value)
}

public func policyDecoy(_ value: Int) -> Statement {
  let normalized = normalize(value) + policyFee(value)
  return Statement(total: normalized, label: "invoice")
}

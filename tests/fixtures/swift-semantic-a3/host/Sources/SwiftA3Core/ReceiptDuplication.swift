public struct Receipt {
  public let cents: Int
  public let code: String

  public init(cents: Int, code: String) {
    self.cents = cents
    self.code = code
  }

  public init(cents: Double, code: String) {
    self.cents = Int(cents)
    self.code = code
  }
}

private func roundCents(_ value: Int) -> Int {
  value * 100
}

public func makeReceipt(_ value: Int) -> Receipt {
  let cents = roundCents(value)
  return Receipt(cents: cents, code: "sale")
}

public func summarizeReceipt(_ value: Int) -> Receipt {
  let amount = roundCents(value)
  let code = "sale"
  return Receipt(cents: amount, code: code)
}

public func receiptFactoryReference(_ value: Int) -> Receipt {
  let factory: (Int) -> Receipt = makeReceipt
  _ = factory
  return Receipt(cents: value, code: "reference")
}

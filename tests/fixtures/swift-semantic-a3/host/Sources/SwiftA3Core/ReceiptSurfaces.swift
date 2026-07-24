public func checkoutReceipt(_ value: Int) {
  _ = makeReceipt(value)
}

public func receiptTotal(_ value: Int) -> Int {
  summarizeReceipt(value).cents
}

public func queuedInvoiceTotal(_ amounts: [Int]) -> Int {
  var total = 0
  for amount in amounts {
    total += amount
  }
  return total
}

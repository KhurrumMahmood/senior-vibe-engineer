// decision:6006
public func externalHotspot(_ value: Int) -> Int {
  if value > 0 && value < 10 || value == 20 { return 1 }
  if value > 1 && value < 11 || value == 21 { return 2 }
  return (try? parseInvoice("external")) ?? 0
}

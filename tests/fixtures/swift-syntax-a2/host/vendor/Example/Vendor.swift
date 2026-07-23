// decision:6002
func vendorHotspot(_ value: Int) -> Int {
  if value > 0 && value < 10 || value == 20 { return 1 }
  if value > 1 && value < 11 || value == 21 { return 2 }
  return (try? parseInvoice("vendor")) ?? 0
}

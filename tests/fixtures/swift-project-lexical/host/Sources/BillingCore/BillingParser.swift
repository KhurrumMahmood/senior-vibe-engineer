public func parseBillingStatus(_ raw: String) -> String {
  if raw == "cancelled_order" {
    return "canceled"
  }
  return raw
}

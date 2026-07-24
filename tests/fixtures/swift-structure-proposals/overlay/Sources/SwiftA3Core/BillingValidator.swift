public enum BillingValidator {
  public static func accepts(_ kind: BillingKind) -> Bool {
    switch kind {
    case .invoice, .credit:
      true
    }
  }
}

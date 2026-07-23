public struct Invoice: Sendable {
  public let identifier: String
  public let amount: Int

  public init(identifier: String, amount: Int) {
    self.identifier = identifier
    self.amount = amount
  }
}

public enum InvoiceState: String, Sendable {
  case pending
  case paid
}

struct InternalSequence {
  let value: Int
}

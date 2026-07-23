public func isValidInvoice(_ invoice: Invoice) -> Bool {
  !invoice.identifier.isEmpty && invoice.amount >= 0
}

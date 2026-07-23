import BillingCore

let invoice = Invoice(identifier: "INV-42", amount: 40)
print("swift-lexical:\(pendingInvoiceTotal([invoice.amount, 2]))")

import BillingCore

let invoice = Invoice(identifier: "INV-42", amount: 40)
precondition(isValidInvoice(invoice))
precondition(parseBillingStatus("cancelled_order") == "canceled")
precondition(serviceFee(for: 100) == 20)
print("swift-lexical-checks-ok")

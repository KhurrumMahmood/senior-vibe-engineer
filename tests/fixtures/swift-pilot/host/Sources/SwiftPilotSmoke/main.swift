import BillingCore

let service = InvoiceService(clock: FixedClock())
print(service.issue(identifier: "INV-42"))

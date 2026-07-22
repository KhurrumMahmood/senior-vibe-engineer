import BillingCore

func inventoryOnlySmokeExpectation() -> String {
    InvoiceService(clock: FixedClock()).issue(identifier: "TEST-1")
}

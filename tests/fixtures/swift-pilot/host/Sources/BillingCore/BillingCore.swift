public protocol Clock {
    func now() -> String
}

public struct FixedClock: Clock {
    public init() {}

    public func now() -> String {
        "fixed-2026"
    }
}

public struct Invoice {
    public let identifier: String

    public init(identifier: String) {
        self.identifier = identifier
    }
}

public struct InvoiceFormatter {
    public init() {}

    public func render(_ invoice: Invoice, at timestamp: String) -> String {
        "invoice:\(invoice.identifier):\(timestamp)"
    }
}

public struct InvoiceService {
    private let clock: any Clock
    private let formatter: InvoiceFormatter

    public init(clock: any Clock, formatter: InvoiceFormatter = InvoiceFormatter()) {
        self.clock = clock
        self.formatter = formatter
    }

    public func issue(identifier: String) -> String {
        formatter.render(Invoice(identifier: identifier), at: clock.now())
    }
}

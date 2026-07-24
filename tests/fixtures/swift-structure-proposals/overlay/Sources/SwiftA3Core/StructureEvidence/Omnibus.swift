public enum DomainOperations {
  public static func loadPayments() -> Int { 1 }
  public static func savePayments() -> Int { 2 }
  public static func loadCustomers() -> Int { 3 }
  public static func saveCustomers() -> Int { 4 }
  public static func loadExports() -> Int { 5 }
  public static func saveExports() -> Int { 6 }
  public static func renderExports() -> Int { 9 }
  public static func loadNotifications() -> Int { 7 }
  public static func saveNotifications() -> Int { 8 }
}

public func exportSurface() -> Int {
  DomainOperations.loadExports()
    + DomainOperations.saveExports()
    + DomainOperations.renderExports()
}

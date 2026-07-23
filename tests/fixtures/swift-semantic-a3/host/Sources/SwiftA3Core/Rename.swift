public struct LegacyStatus {
  public let rawValue: String

  public init(rawValue: String) {
    self.rawValue = rawValue
  }
}

public enum CanonicalStatus: String {
  case ready
}

public func transition(_ status: LegacyStatus) -> CanonicalStatus {
  status.rawValue.isEmpty ? .ready : .ready
}

// LegacyStatus remains in compatibility documentation, not symbol identity.
public let reflectedLegacyStatusName = "LegacyStatus"

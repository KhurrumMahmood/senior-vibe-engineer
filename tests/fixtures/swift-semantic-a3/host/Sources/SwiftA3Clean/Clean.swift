public enum CleanState: String {
  case ready
}

public struct CleanJob {
  public var state: CleanState

  public init(state: CleanState) {
    self.state = state
  }
}

public func cleanCharge(_ value: Int, audit: Bool) -> Int {
  value + (audit ? 1 : 0)
}

public func cleanSummary(_ value: Int) -> String {
  "clean:\(value)"
}

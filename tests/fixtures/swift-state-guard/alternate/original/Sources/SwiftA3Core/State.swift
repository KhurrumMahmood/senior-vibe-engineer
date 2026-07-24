public enum DownloadPhase: String {
  case waiting = "not-started"
  case active = "in-progress"
  case finished = "completed"
}

public final class Download {
  private(set) var phase: String

  public init() {
    phase = "not-started"
  }

  public func start() {
    phase = "in-progress"
  }

  public func finish() {
    phase = "completed"
  }

  public func isActive() -> Bool {
    phase == "in-progress"
  }
}

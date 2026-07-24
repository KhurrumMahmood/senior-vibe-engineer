public enum DownloadPhase: String {
  case waiting = "not-started"
  case active = "in-progress"
  case finished = "completed"
}

public final class Download {
  private(set) var phase: DownloadPhase

  public init() {
    phase = .waiting
  }

  public func start() {
    phase = .active
  }

  public func finish() {
    phase = .finished
  }

  public func isActive() -> Bool {
    phase == .active
  }
}

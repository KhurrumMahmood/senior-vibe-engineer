public enum JobState: String {
  case queued
  case running
  case done
}

public final class Job {
  private(set) var state: String

  public init() {
    state = "queued"
  }

  public func start() {
    state = "running"
  }

  public func finish() {
    state = "done"
  }

  public func isRunning() -> Bool {
    state == "running"
  }
}

public struct TypedJob {
  public var state: JobState

  public init(state: JobState) {
    self.state = state
  }
}

public struct WirePayload: Codable {
  public var status: String

  public init(status: String) {
    self.status = status
  }
}

public final class OneShot {
  private var phase = "new"

  public init() {}

  public func close() {
    phase = "closed"
  }
}

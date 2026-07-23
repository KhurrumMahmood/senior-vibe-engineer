public func charge(_ identifier: String, audit: Bool = false) -> Int {
  identifier.count + (audit ? 1 : 0)
}

public func legacyChargePath() -> Int {
  charge("legacy")
}

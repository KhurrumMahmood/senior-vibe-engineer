public func recordStatement(_ value: Int) {
  _ = buildStatement(value)
}

public func statementTotal(_ value: Int) -> Int {
  buildStatement(value).total
}

public func statementFactoryReference(_ value: Int) -> Statement {
  let factory: (Int) -> Statement = buildStatement
  _ = factory
  return Statement(total: value, label: "reference")
}

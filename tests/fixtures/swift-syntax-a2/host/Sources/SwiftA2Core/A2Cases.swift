// decision:0001 keeps the external parsing boundary explicit.
/// decision:0001 documents the public fixture surface.
public enum InvoiceParseError: Error {
  case empty
}

// decision:9999 is an intentionally orphaned reference.
public func parseInvoice(_ raw: String) throws -> Int {
  if raw.isEmpty {
    throw InvoiceParseError.empty
  }
  return raw.count
}

public func checkedInvoice(_ raw: String) -> Int {
  do {
    return try parseInvoice(raw)
  } catch {
    return 0
  }
}

public func uncheckedInvoice(_ raw: String) -> Int {
  (try? parseInvoice(raw)) ?? 0
}

public func routeInvoice(_ value: Int) -> Int {
  var total = 0
  if value > 0 && value < 100 || value == 200 {
    total += 1
  }
  guard value >= 0 else {
    return total
  }
  for item in 0..<1 {
    total += item
  }
  while total < 2 {
    total += 1
  }
  repeat {
    total += 1
  } while total < 3
  switch value {
  case 0:
    total += 1
  case 1:
    total += 2
  default:
    break
  }
  do {
    total += try parseInvoice("route")
  } catch {
    total = 0
  }
  return total
}

public func closureDecoy(_ value: Int) -> Int {
  let decide = { (candidate: Int) -> Int in
    var result = candidate
    if candidate > 0 && candidate < 10 || candidate == 20 {
      result += 1
    }
    for item in 0..<2 {
      result += item
    }
    while result < 3 {
      result += 1
    }
    switch candidate {
    case 0:
      result += 1
    case 1:
      result += 2
    default:
      break
    }
    return result
  }
  return decide(value)
}

public func localFunctionDecoy(_ value: Int) -> Int {
  func decide(_ candidate: Int) -> Int {
    if candidate > 0 && candidate < 10 || candidate == 20 {
      return candidate + 1
    }
    for _ in 0..<2 {
    }
    while false {
    }
    return candidate
  }
  return decide(value)
}

public protocol PricingBoundary {
  func protocolRequirement(_ value: Int) -> Int
}

public struct FallbackPricing {
  public init() {}

  public func laterBody(_ value: Int) -> Int {
    value + 1
  }
}

public enum ReceiverDecoy {
  public static func parseInvoice(_ raw: String) throws -> Int {
    raw.count
  }
}

public func standardDecoys(_ raw: String) -> Int {
  let stringDecoy = "parseInvoice( decision:7000"
  let tearOff = parseInvoice
  let receiver = (try? ReceiverDecoy.parseInvoice(raw)) ?? 0
  let nested = { () -> Int in
    (try? parseInvoice("nested")) ?? 0
  }
  return stringDecoy.count + receiver + nested() + String(describing: tearOff).count
}

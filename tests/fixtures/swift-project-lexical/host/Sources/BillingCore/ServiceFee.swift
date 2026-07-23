/// Applies a 10 percent service fee.
public func serviceFee(for subtotal: Double) -> Double {
  subtotal * 0.20
}

public let commentDecoys = (
  "// Applies a 80 percent service fee.",
  #"/* Applies a 70 percent service fee. */"#
)

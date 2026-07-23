// swift-tools-version: 6.0

import PackageDescription

let package = Package(
  name: "SwiftProjectLexical",
  products: [
    .library(name: "BillingCore", targets: ["BillingCore"]),
    .executable(name: "swift-lexical-smoke", targets: ["SwiftLexicalSmoke"]),
    .executable(name: "swift-lexical-check", targets: ["SwiftLexicalCheck"]),
  ],
  targets: [
    .target(name: "BillingCore"),
    .executableTarget(name: "SwiftLexicalSmoke", dependencies: ["BillingCore"]),
    .executableTarget(name: "SwiftLexicalCheck", dependencies: ["BillingCore"]),
  ]
)

// swift-tools-version: 6.0

import PackageDescription

let package = Package(
  name: "SwiftSyntaxA2",
  products: [
    .library(name: "SwiftA2Core", targets: ["SwiftA2Core"]),
    .executable(name: "swift-a2-check", targets: ["SwiftA2Check"]),
    .executable(name: "swift-a2-smoke", targets: ["SwiftA2Smoke"]),
  ],
  targets: [
    .target(name: "SwiftA2Core"),
    .target(name: "SwiftA2Clean"),
    .executableTarget(name: "SwiftA2Check", dependencies: ["SwiftA2Core"]),
    .executableTarget(name: "SwiftA2Smoke", dependencies: ["SwiftA2Core"]),
  ]
)

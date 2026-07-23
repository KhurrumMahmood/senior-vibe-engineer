// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SwiftSemanticA3",
    products: [
        .library(name: "SwiftA3Core", targets: ["SwiftA3Core"]),
        .library(name: "SwiftA3Clean", targets: ["SwiftA3Clean"]),
        .executable(name: "swift-a3-check", targets: ["SwiftA3Check"]),
        .executable(name: "swift-a3-smoke", targets: ["SwiftA3Smoke"]),
    ],
    targets: [
        .target(name: "SwiftA3Core"),
        .target(name: "SwiftA3Clean"),
        .executableTarget(
            name: "SwiftA3Check",
            dependencies: ["SwiftA3Core", "SwiftA3Clean"]
        ),
        .executableTarget(name: "SwiftA3Smoke", dependencies: ["SwiftA3Core"]),
    ]
)

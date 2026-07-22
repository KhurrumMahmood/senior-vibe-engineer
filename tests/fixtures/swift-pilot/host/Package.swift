// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SwiftPilot",
    products: [
        .library(name: "BillingCore", targets: ["BillingCore"]),
        .executable(name: "swift-pilot-smoke", targets: ["SwiftPilotSmoke"]),
    ],
    targets: [
        .target(name: "BillingCore"),
        .executableTarget(name: "SwiftPilotSmoke", dependencies: ["BillingCore"]),
    ]
)

// swift-tools-version: 5.9
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "swiftcog",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(
            name: "SwiftCogGUI",
            targets: ["SwiftCogGUI"]),
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-argument-parser.git", from: "1.2.0"),
        .package(url: "https://github.com/OpenDive/OpenAIKit.git", from: "2.0.1")
    ],
    targets: [
        .target(
            name: "SwiftCogCore",
            dependencies: [
                .product(name: "OpenAIKit", package: "OpenAIKit"),
                .product(name: "ArgumentParser", package: "swift-argument-parser")
            ]
        ),
        .executableTarget(
            name: "SwiftCogGUI",
            dependencies: [
                "SwiftCogCore",
                .product(name: "OpenAIKit", package: "OpenAIKit")
            ],
            path: "Sources/SwiftCogGUI",
            resources: [.process("Resources/chat.html")],
            linkerSettings: [
                .linkedFramework("Vision"),
                .linkedFramework("AVFoundation")
            ]
        ),
    ]
)

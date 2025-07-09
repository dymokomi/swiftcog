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
            name: "SwiftCog",
            targets: ["SwiftCog"]),
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-argument-parser.git", from: "1.2.0"),
        .package(url: "https://github.com/OpenDive/OpenAIKit.git", from: "2.0.1"),
        .package(url: "https://github.com/swiftpackages/DotEnv.git", from: "3.0.0")
    ],
    targets: [
        .target(
            name: "SwiftCogCore",
            dependencies: [
                .product(name: "OpenAIKit", package: "OpenAIKit"),
                .product(name: "ArgumentParser", package: "swift-argument-parser")
            ]
        ),
        .target(
            name: "Examples",
            dependencies: ["SwiftCogCore"],
            path: "Sources/Examples",
            resources: [.process("ExampleApp/chat.html")]
        ),
        .executableTarget(
            name: "SwiftCog",
            dependencies: [
                "SwiftCogCore",
                "Examples",
                .product(name: "ArgumentParser", package: "swift-argument-parser"),
                .product(name: "DotEnv", package: "DotEnv")
            ],
            path: "Sources/SwiftCog"
        ),
    ]
)

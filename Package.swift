// swift-tools-version: 6.1
import PackageDescription

let package = Package(
    name: "swift-nested-sources",
    products: [
        .plugin(name: "NestedSources", targets: ["NestedSources"]),
    ],
    targets: [
        .plugin(name: "NestedSources", capability: .buildTool()),
        // Lists only its anchor file, so the rest of the folder compiles only through the plugin.
        .testTarget(name: "NestedSourcesTests", sources: ["NestedSourcesTests.swift"], plugins: ["NestedSources"]),
    ]
)

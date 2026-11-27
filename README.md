# NestedSources Plugin

A SwiftPM build tool plugin that lets one module contain several files with the same name in different folders.

## The Problem

Swift rejects two files with the same name in one module:

```
error: filename "Service.swift" used twice
```

So a module can't hold `Jobs/Service.swift` next to `Runs/Service.swift`, and folders end up with prefixed names like `JobsService.swift` just to keep the compiler happy.

## How It Works

1. The target lists only one anchor file in `sources:`, e.g. `sources: ["Billing.swift"]`.
2. On every build, the plugin finds every other `.swift` file in the target's folder.
3. It symlinks each one into its work directory under a unique name: `Jobs/Service.swift` becomes `Jobs%2FService.swift`.
4. The compiler sees unique filenames. Build errors name the link, e.g. `.build/…/NestedSources/Jobs%2FService.swift:2:21`, so the file name still tells you which original to open.

Editors need one extra step, see [Editor Support](#editor-support).

Because the plugin scans the folder on every build, new files need no manifest change.

## Installation

```swift
dependencies: [
    .package(url: "https://github.com/alexeichhorn/swift-nested-sources.git", from: "0.1.0")
]
```

Then add the plugin to a target, give it an explicit `path:`, and list only its anchor file:

```swift
.target(
    name: "Billing",
    path: "Sources/Billing",
    sources: ["Billing.swift"],
    plugins: [.plugin(name: "NestedSources", package: "swift-nested-sources")]
)
```

```
Sources/Billing/
├── Billing.swift        ← compiled directly
├── Jobs/Service.swift   ← compiled through the plugin
└── Runs/Service.swift   ← compiled through the plugin
```

The anchor can be any file in the folder; for an executable target, the file with `@main` is a natural choice.

## Recommended Setup

Declaring every target this way gets repetitive. Two small helpers in your `Package.swift` keep each target to one line. A manifest can't import code from a dependency, so copy these lines into your own `Package.swift`:

```swift
/// A library in `Sources/<name>/` whose anchor file is `<name>.swift`; NestedSources compiles the rest of the folder.
func module(_ name: String, dependencies: [Target.Dependency] = []) -> Target {
    .target(
        name: name,
        dependencies: dependencies,
        path: "Sources/\(name)",
        sources: ["\(name).swift"],
        plugins: [.plugin(name: "NestedSources", package: "swift-nested-sources")]
    )
}

/// An executable in `Sources/<name>/` whose anchor file `<name>.swift` holds `@main`.
func app(_ name: String, dependencies: [Target.Dependency] = []) -> Target {
    .executableTarget(
        name: name,
        dependencies: dependencies,
        path: "Sources/\(name)",
        sources: ["\(name).swift"],
        plugins: [.plugin(name: "NestedSources", package: "swift-nested-sources")]
    )
}

let package = Package(
    name: "MyProject",
    dependencies: [
        .package(url: "https://github.com/alexeichhorn/swift-nested-sources.git", from: "0.1.0")
    ],
    targets: [
        module("Billing"),
        app("Server", dependencies: ["Billing"]),
    ]
)
```

## Requirements

- Swift 6.1 or later (`swift-tools-version: 6.1`).
- macOS or Linux. The plugin links files with `/bin/ln`, so it doesn't run on Windows.

## Editor Support

SourceKit-LSP only knows the symlinks the plugin compiles, not the files you edit. Opening `Jobs/Service.swift` in an editor therefore gets no completion, diagnostics or jump-to-definition. [`Tools/sourcekit-nested-sources.py`](Tools/sourcekit-nested-sources.py) fixes that: it starts SourceKit-LSP and maps file paths between the originals and the symlinks in both directions.

This works in editors that let you choose the language server binary, such as Zed, VS Code and Cursor. Xcode is not supported. To set it up:

1. Copy `Tools/sourcekit-nested-sources.py` into your package. It finds the package by walking up to the nearest `Package.swift`. It needs `python3` (3.9 or later).
2. Add `.sourcekit-lsp/config.json` next to your `Package.swift`. SourceKit-LSP must index with Swift Build, because SwiftPM's native build system writes the compiler outputs of plugin-generated files into the project root:

   ```json
   {
     "swiftPM": {
       "buildSystem": "swiftbuild",
       "scratchPath": ".build/index-build"
     }
   }
   ```

3. Point your editor at the script. Paths are relative to the folder you open in the editor.

   Zed, `.zed/settings.json` (excluding `.build` stops a reload loop while indexing):

   ```json
   {
     "file_scan_exclusions": ["**/.build", "..."],
     "lsp": {
       "sourcekit-lsp": {
         "binary": {
           "path": "/usr/bin/env",
           "arguments": ["python3", "Tools/sourcekit-nested-sources.py"]
         }
       }
     }
   }
   ```

   VS Code and Cursor with the Swift extension, `.vscode/settings.json`:

   ```json
   {
     "swift.sourcekit-lsp.serverPath": "${workspaceFolder}/Tools/sourcekit-nested-sources.py"
   }
   ```

The proxy learns about a new file once indexing has linked it. A file opened before then, such as a newly added one, switches over by itself once the link exists, unless it was edited in the meantime; then reopen it.

This repository uses the same setup for its own test target.

## Notes

- `swift build` runs the plugin without any prompt. Xcode asks you to trust a build plugin from another package the first time; on CI, `xcodebuild` needs `-skipPackagePluginValidation`.
- Every `.swift` file under the target's folder is compiled, including ones in nested folders. Keep files that shouldn't be part of the module outside it.

## License

MIT. See [LICENSE](LICENSE).

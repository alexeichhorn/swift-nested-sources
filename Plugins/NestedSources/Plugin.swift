import Foundation
import PackagePlugin

/// Compiles every Swift file of a module that its `sources:` doesn't list, under a unique name.
///
/// Swift rejects two files with the same name in one module, which rules out `Jobs/Service.swift` next to
/// `Runs/Service.swift`. Each module therefore lists only its anchor file in `sources:`, and this plugin links all other
/// files into its work directory as e.g. `Jobs%2FService.swift`. It scans on every build, so new files need no manifest
/// change.
@main
struct NestedSources: BuildToolPlugin {
    func createBuildCommands(context: PluginContext, target: Target) throws -> [Command] {
        let directory = target.directoryURL.resolvingSymlinksInPath()
        // `sourceFiles` also lists the files `sources:` left out, typed `.unknown`.
        let compiledDirectly = Set(
            target.sourceModule?.sourceFiles.filter { $0.type == .source }.map { $0.url.resolvingSymlinksInPath().path } ?? []
        )
        let paths = try FileManager.default.subpathsOfDirectory(atPath: directory.path)

        return paths.filter { $0.hasSuffix(".swift") }.sorted().compactMap { relativePath in
            let source = directory.appendingPathComponent(relativePath)
            guard !compiledDirectly.contains(source.path) else { return nil }
            // Escape separators without conflating folder names with underscores.
            let filename =
                relativePath
                .replacingOccurrences(of: "%", with: "%25")
                .replacingOccurrences(of: "/", with: "%2F")
            let output = context.pluginWorkDirectoryURL.appendingPathComponent(filename)
            // Symlinks let SourceKit navigate to the originals while the compiler sees unique filenames.
            return .buildCommand(
                displayName: "Link \(target.name)/\(relativePath)",
                executable: URL(fileURLWithPath: "/bin/ln"),
                arguments: ["-sf", source.path, output.path],
                inputFiles: [source],
                outputFiles: [output]
            )
        }
    }
}

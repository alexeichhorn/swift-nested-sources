import Testing

/// The files beside this one repeat a filename and are not listed in `sources:`; they only compile through the plugin.
@Test func filesOutsideSourcesCompileIntoTheModule() {
    #expect(JobService().name == "jobs")
    #expect(RunService().name == "runs")
    #expect(defaultConcurrency == 4)
}

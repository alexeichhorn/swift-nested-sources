#!/usr/bin/env python3
"""Runs SourceKit-LSP behind a proxy that maps nested source files to their compiled symlinks.

The `NestedSources` plugin compiles `Jobs/Service.swift` as a symlink such as `Jobs%2FService.swift`, and SourceKit-LSP
only knows that path. The editor opens the original, so this proxy rewrites document URIs to the symlink on the way in
and back to the original on the way out. Message text and source contents pass through unchanged.

Copy it anywhere inside your package and let the editor launch it instead of `sourcekit-lsp`; any arguments are
forwarded. It serves the nearest folder above it that holds a `Package.swift`. Runs on Python 3.9 and later.

SourceKit-LSP must index with Swift Build into `.build/index-build` (`.sourcekit-lsp/config.json`): SwiftPM's native
build system writes the compiler outputs of plugin-generated files into the project root.
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import IO, Any

script = Path(__file__).resolve()
package = next(folder for folder in script.parents if (folder / "Package.swift").is_file())
# `swiftPM.scratchPath` in `.sourcekit-lsp/config.json`. It is relative to the server's working directory, so `main`
# starts the server inside the package; the index then lands here wherever the editor was opened.
scratch = package / ".build/index-build"


def symlink_uris() -> dict[str, str]:
    """Maps each original file URI to the symlink SourceKit-LSP compiles."""
    outputs = scratch / "plugins/outputs"
    return {
        path.resolve().as_uri(): path.as_uri()
        for path in outputs.glob("*/*/destination/NestedSources/*.swift")
        if path.is_symlink()
    }


def remap(value: Any, uris: dict[str, str]) -> Any:
    if isinstance(value, list):
        return [remap(item, uris) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in {"uri", "targetUri", "oldUri", "newUri"} and isinstance(item, str):
            result[key] = uris.get(item, item)
        elif key == "changes" and isinstance(item, dict):
            result[key] = {uris.get(uri, uri): remap(edits, uris) for uri, edits in item.items()}
        else:
            result[key] = remap(item, uris)
    return result


def read_message(stream: IO[bytes]) -> dict[str, Any] | None:
    headers = {}
    while line := stream.readline():
        if line == b"\r\n":
            break
        name, value = line.decode("ascii").split(":", 1)
        headers[name.lower()] = value.strip()
    if not headers:
        return None
    return json.loads(stream.read(int(headers["content-length"])))


def write_message(stream: IO[bytes], message: Any):
    body = json.dumps(message, ensure_ascii=False).encode("utf-8")
    stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    stream.flush()


def main():
    # Outside macOS, `sourcekit-lsp` ships next to `swift` on the PATH.
    server_command = ["xcrun", "sourcekit-lsp"] if sys.platform == "darwin" else ["sourcekit-lsp"]
    # The editor already asked whether to trust this project before running this script, so `.sourcekit-lsp/config.json`
    # can load without SourceKit-LSP's own trust prompt. Builds without that prompt don't know the flag.
    help_text = subprocess.run([*server_command, "--help"], capture_output=True, text=True).stdout
    trust = ["--bypass-workspace-trust"] if "--bypass-workspace-trust" in help_text else []
    command = [*server_command, *trust, *sys.argv[1:]]
    server = subprocess.Popen(command, cwd=package, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    to_server, from_server = server.stdin, server.stdout
    assert to_server is not None and from_server is not None
    signal.signal(signal.SIGTERM, lambda *_: server.terminate())

    def forward_editor_messages():
        try:
            while (message := read_message(sys.stdin.buffer)) is not None:
                write_message(to_server, remap(message, symlink_uris()))
        except (OSError, ValueError, KeyError) as error:
            print(f"sourcekit-nested-sources: forwarding to SourceKit-LSP failed: {error}", file=sys.stderr)
        finally:
            to_server.close()

    threading.Thread(target=forward_editor_messages, daemon=True).start()
    try:
        while (message := read_message(from_server)) is not None:
            originals = {symlink: original for original, symlink in symlink_uris().items()}
            write_message(sys.stdout.buffer, remap(message, originals))
    finally:
        if server.poll() is None:
            server.terminate()
        server.wait()


if __name__ == "__main__":
    main()

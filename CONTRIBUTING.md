# Contributing

Use a feature branch for changes. Follow [building](docs/building.md) for setup, then run lint, formatting, tests and schema checks. Add tests for behavioral changes, especially malformed input, source protection, conflict handling, stale plans and failures before output commit. Use original synthetic fixtures.

Keep transport adapters thin: shared behavior belongs in the service, workspace and codecs so GUI, CLI and MCP agree. Public operations need type annotations, docstrings, discoverable JSON schemas and working examples. Distinguish opaque copying from decoding, and structural verification from engine testing.

Document sources and licenses for contributed code, format references and assets. Retain third-party notices. Contributions must be compatible with the applicable project licenses.

Submit a pull request describing the problem, resulting behavior, validation and limitations. Maintainers review and merge changes through pull requests. Do not push directly to the default branch.

For substantial format additions, describe supported versions, preservation rules, size limits and failure behavior before implementation. [Format references](docs/format-references.md) explains the current layouts and attribution requirements.

# Contributing

Use a feature branch for changes. Follow [docs/building.md](docs/building.md) for setup, then run formatting checks, tests and schema generation. Add tests for behavioral changes, especially malformed input, source protection, conflict handling, stale plans and failures before output commit. Use original synthetic fixtures; do not commit extracted game content.

Keep transport code thin: changes to behavior belong in the shared service/workspace/codecs so GUI, CLI and MCP agree. Public operations need type annotations, docstrings, discoverable JSON schemas and working examples. Do not describe opaque copying as format decoding or structural checks as game testing.

Document the source and license of new layout knowledge, code and assets. Retain third-party notices. Contributors must have the right to submit their contributions under the project's applicable licenses. No separate contributor agreement is currently used.

Submit a pull request when the repository owner makes that workflow available. Include the problem, final behavior, tests and limitations. Do not commit directly to the default branch. Do not push, create PRs or merge on the owner's behalf without authorization.

For substantial format support, first discuss the supported versions, preservation rules, maximum sizes, failure behavior and provenance. Animation codec and character-preview work needs the unresolved review in [docs/provenance.md](docs/provenance.md) addressed first.

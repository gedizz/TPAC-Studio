# Directory and architecture map

```text
TPAC-Studio/
  README.md                 Entry point, installation and feature matrix
  LICENSE                   MIT for original eligible work
  NOTICE                    Retained upstream attribution
  THIRD_PARTY_NOTICES.md     Dependency roles and license references
  LICENSES/                 Full upstream notice and license index
  pyproject.toml            Package, dependency extras and executable entry points
  requirements-lock.txt     Tested Windows dependency snapshot
  AGENTS.md                 Contributor/AI rules
  CONTRIBUTING.md            Development and review workflow
  SECURITY.md                Trust boundaries and reporting
  CHANGELOG.md               Release scope
  .gitignore                Generated files, user assets and secrets
  .gitattributes            Text/binary conventions
  .github/workflows/        Source lint/tests/wheel CI
  src/tpac_studio/
    core.py                 Bounded TPAC I/O, source hashes, immutable records
    workspace.py            Selection, conflict resolution, undo, plans and persistence
    service.py              Shared operations, schemas and structured results
    settings.py             Editable-field definitions and validation
    textures.py             Image import / supported texture decode
    models.py               Static model orchestration and assembly
    blender_import.py       Isolated optional Blender process script
    mesh_encoding.py        Static stream and metadata serialization
    mesh_validation.py      Vertex stream offset/stride checks
    mesh_preview.py         Supported mesh/material decoding
    particles.py            Bounded particle parsing and field edits
    demo.py                 Original procedural fixtures
    extensions.py           Opt-in provider registration contract
    cli.py                  One-request JSON command-line adapter
    mcp_server.py           Official SDK stdio adapter
    gui.py                  Qt workspace frontend
    viewport.py             Independent OpenGL preview
    desktop_check.py        Original-example Qt/OpenGL startup check
    errors.py               Structured errors and explicit runtime checks
    schemas/                Generated operation/settings snapshots
    py.typed                Typing marker
  examples/                 Original, runnable automation/provider examples
  tests/                    Synthetic fixtures, failure cases, CLI and MCP tests
  tools/                    Schema generation, GUI checks and executable build helper
  docs/                     Usage, API, provenance, format and release documentation
```

## Dependency direction

GUI / CLI / MCP call `Studio`; it owns one `Workspace` and an extension registry. Workspaces manage immutable `Asset` and `Segment` values from `core`. Codecs return replacements; they do not directly commit workspace mutations. The optional GUI is the only consumer of Qt/OpenGL; the core service is usable headlessly. NumPy is used by the preview, not by container assembly.

A loaded package holds bounded metadata and file-backed segments. A source fingerprint prevents silently rebuilding from changed input. Edits create new values and revisioned snapshots; up to 30 snapshots enable session undo. Saved workspaces embed their backing data rather than trusting external extraction paths.

Builds have two stages. Planning identifies exact content and incomplete dependency findings. Execution recomputes that plan, streams to a temporary file, reads it back, compares fingerprints and commits a single output. All interfaces use that same writer. There is no separate unsafe agent writer.

## Extension boundaries

Providers return metadata or a replacement asset through a declared settings schema. Identity/name/type constraints are enforced on commit. A host explicitly installs/enables providers; assets cannot request plugin imports. Providers are trusted Python code and are not isolated. Read the [extension guide](extensions.md) before implementing one.

## Design decisions

- Unknown records are preserved; unsupported decoding is reported separately.
- Reference detection is deliberately labelled incomplete, not silently treated as certification.
- No game DLL or engine renderer is loaded; preview results are approximations.
- Headless operations never show modal dialogs.
- Filesystem roots and revision guards prevent common automation mistakes; they are not a hostile-code sandbox.
- Source distribution contains no game assets, imported models, private captures or compiled engine code.
- No audio playback, mixer manipulation or game-option editing exists in this project.

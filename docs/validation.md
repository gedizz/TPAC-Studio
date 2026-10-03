# Testing and validation

TPAC Studio 1.0.0 targets Windows x64. The reference test environment uses Python 3.12.14, Qt/PySide 6.11.2 and Blender 5.1. Exact Python dependency versions are recorded in [dependency-inventory.json](dependency-inventory.json).

## Automated coverage

The 37-test suite uses original synthetic data and covers:

- TPAC v2 round trips, independently assembled v1 inputs and raw/LZ4/unknown storage preservation.
- Invalid containers, conflicting identities, changed inputs and protected source/hardlink paths.
- Stale revisions and build plans, failed writes and temporary-file cleanup.
- Self-contained workspaces, concurrent saves, unexpected ZIP entries and rooted CLI paths.
- Texture import, static geometry decoding, particle edits and session undo.
- Extension schemas, identity constraints and JSON output validation.
- JSON CLI workflows and an actual MCP client/server exchange over stdio.

Run the suite, lint and schema checks using [the build guide](building.md). GUI checks are separate: `python tools/check_gui.py --output local/gui-check` renders original texture, mesh and particle examples and saves screenshots and structured results. The packaged executable supports the same check through `--check-startup --output <folder>`.

## Interpreting results

Structural verification checks container bounds and record fingerprints. It does not validate all shader behavior, animation semantics, external references or game versions. Test rebuilt packages in their target game environment before deployment.

Particle previews approximate selected emitter fields rather than the native renderer. GUI checks cover sample content and the active graphics driver; they are not exhaustive hardware compatibility tests. Static model JSON and the Blender OBJ bridge have been exercised; the FBX/glTF/BLEND import branches require additional representative format testing.

The Python interfaces are designed to be portable, but Linux and macOS have not been validated. Windows release archives are tested after extraction so missing runtime files are detected. Release checksums identify the exact distributed files.

# Validation record

Candidate: **0.2.0**, checked **2026-10-02** on Windows, Python **3.12.14**. Exact dependency versions and license metadata are in [dependency-inventory.json](dependency-inventory.json). This is a technical test report, not a provenance clearance.

## Completed

| Check | Evidence / result |
| --- | --- |
| Automated tests | **37 passed**, using original synthetic data |
| Formatting and lint | Ruff checks and format checks pass for delivered source, examples, tools and tests |
| API snapshots | Generated operation reference and JSON schemas match live service contracts |
| TPAC I/O | Synthetic v2 round trip; independently assembled v1 input; raw/LZ4/unknown storage preservation |
| Failure handling | Malformed containers, conflicting identities, protected source/hardlink paths, changed sources, stale revisions/plans, failed writes and temporary-file cleanup |
| Saved workspaces | Self-contained reload, concurrent-save rejection, unexpected ZIP-entry rejection, rooted CLI paths and UTF-8 BOM requests |
| Codec workflows | Original RGBA texture, static geometry and supported synthetic particle edits/undo |
| Extension contract | Schema validation, real edit, identity rejection and invalid JSON output |
| JSON CLI | Import, persist project, plan, build; optimized Python still rejects invalid inputs |
| MCP | Real official-SDK stdio initialize, list, call, build, root rejection and resource reads |
| Source GUI | Actual Qt/OpenGL checker, mesh and particle preview; timeline scrubbing; no reported GL/decoder errors |
| Blender bridge | Blender 5.1 imported an original triangle OBJ into three static records |
| Documented Python example | Five original records built and verified, with saved workspace and plan |
| Clean-folder installation | Built a wheel from a fresh copy of the delivered folder, installed it into a separate target using the tested dependency environment, verified imports came from that target, then passed all 37 tests, lint/format/schema checks, documented build workflow and actual GUI checks |
| Python packaging | Wheel and source archive built; licenses/schemas present; no private research directory in archives |
| Windows executable | PyInstaller directory bundle built; actual packaged Qt/OpenGL startup check passed for all three previews, including 14 live particles at the sampled time |

The executable test found an incompatible ICU library selected from the host PATH. The build helper now constrains its child environment's PATH so unrelated native tool directories are not searched. It does not change the user's global PATH. Particle preview tests also caught and fixed timeline-reset and framebuffer alpha-compositing issues.

## Deliberately not claimed

- No game was launched and no new packages were installed into Bannerlord for this release check.
- Structural verification compares container records/payload fingerprints; it cannot certify shaders, animation semantics or every game version.
- No native particle-renderer equivalence, complete dependency graph or production-scale performance benchmark is claimed.
- Only the OBJ path through Blender was exercised; FBX/glTF/BLEND branches share the bridge but were not separately validated against a representative asset library.
- The frozen application's Blender-child branch was not exercised; source-based Blender import was.
- GUI automation sampled original examples, not every dialog/driver/monitor combination. Manual inspection confirmed the recorded previews; this is not exhaustive GUI coverage.
- Linux/macOS execution and the hosted GitHub Actions job have not been run here.
- The exact runtime libraries collected in an executable still require a binary redistribution license review. The delivered GitHub folder contains source, not that bundle.
- Animation authoring/playback and the private prototype's character assets remain excluded pending provenance and scope resolution.

The owner can reproduce the checks in [building.md](building.md). A clean-folder install check and file inventory accompany the delivered candidate. Keep the test report updated rather than converting these qualifications into unsupported release claims.

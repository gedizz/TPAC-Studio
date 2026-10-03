# Provenance and distribution review

Status: **private-review source candidate**, reviewed 2026-10-02. This document records technical evidence and exclusions. It is not a legal opinion, a clean-room certification or permission from TaleWorlds.

## Included work

Original application orchestration, workspace transactions, GUI, API/CLI/MCP adapters, documentation, synthetic examples and tests are offered under MIT, credited to X7 Dragon. File-format work is attributed to the following public MIT source where used or adapted:

- Repository: [szszss/TpacTool](https://github.com/szszss/TpacTool).
- Audited revision: [`b56b77ad273ba67192b1594dbb2eeca8c542b3b7`](https://github.com/szszss/TpacTool/tree/b56b77ad273ba67192b1594dbb2eeca8c542b3b7).
- [Upstream license](https://github.com/szszss/TpacTool/blob/b56b77ad273ba67192b1594dbb2eeca8c542b3b7/LICENSE): MIT, copyright (c) 2020–2022, szszss. A full copy is retained at `LICENSES/TpacTool-MIT.txt`.

| Local area | Reference / origin |
| --- | --- |
| `core.py` | TpacTool `AssetPackage.cs`, `AssetItem.cs`: container tables, asset and segment layouts; new bounded streaming writer and verification |
| `textures.py` | TpacTool texture metadata and pixel-data layouts; original mipmap import using Pillow |
| `particles.py` | TpacTool `ParticleEffectData.cs` traversal; empirically identified editing fields, not an official specification |
| `mesh_encoding.py`, `mesh_validation.py`, `mesh_preview.py`, `models.py` | TpacTool `Metamesh.cs`, `Mesh.cs`, `VertexStreamData.cs`, `Material.cs`; private prototype's empirical stream/packed-tangent work adapted and isolated |
| `demo.py`, tests and examples | Original procedural data created for this project; no sampled game assets |

Names, GUIDs and layout conventions are interoperability references. No shader implementation, TaleWorlds assembly, extracted texture/mesh, decompiled class or native executable is included. The review did **not** establish that every empirical format finding was independently derived in a clean-room process. The development history included engine inspection; changing implementation language or removing binaries does not erase that fact.

## Excluded from this candidate

The earlier private animation decoder/writer explicitly relied on native-reader disassembly. The bundled preview character and human skeleton came from game data. Their redistribution basis was not established. This candidate therefore contains neither that animation implementation nor those assets. Opaque container-level copying of animation records remains supported. No newly invented claim of permission substitutes for that missing evidence.

Also excluded: engine/game DLLs and executables, game and mod TPACs, weapon assets, sound files, extracted/researched source dumps, disassembly scripts, local game paths, screenshots of proprietary assets, personal logs, environments, built application directories and credentials.

The choice to omit the animation workflows from the first public scope still needs the owner's confirmation. If animation playback/authoring is essential to the first release, that portion is blocked pending rights/provenance resolution or an independently supportable replacement. The source candidate is useful without it but is not feature-equivalent to the private prototype.

## TaleWorlds terms and unresolved questions

The [TaleWorlds Modding Tools License Agreement](https://www.taleworlds.com/en/static/mtla) includes restrictions related to reverse engineering and conditions on modding tools/mod distribution. The audit found reasons to investigate applicability, not a basis to promise there is no violation. A permissive license on an upstream reader does not grant rights to a separate company's software or waive terms that may apply to prior research.

Before making the repository public, the owner should resolve the intended distribution scope and the rights question concerning prior native-engine-derived work. Written clarification from TaleWorlds or qualified legal advice may be appropriate. A private GitHub upload is not itself legal clearance.

## Release practices

Retain `LICENSE`, `NOTICE`, upstream attribution and dependency notices. Use original or properly licensed samples only. Do not publish users' saved workspaces by default: they contain source paths and embedded assets. Review changes to codecs for provenance at review time, and record new references with exact upstream revisions and license terms.

Qt/PySide, Pillow, LZ4, MCP and other dependencies keep their licenses. Distributing a bundled executable adds obligations beyond this source-only folder; see [building.md](building.md) and [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

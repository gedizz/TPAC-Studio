# File-format references and attribution

TPAC Studio's container and supported asset layouts reference the MIT-licensed [TpacTool](https://github.com/szszss/TpacTool) project by szszss.

- Reference revision: [`b56b77ad273ba67192b1594dbb2eeca8c542b3b7`](https://github.com/szszss/TpacTool/tree/b56b77ad273ba67192b1594dbb2eeca8c542b3b7).
- Copyright: (c) 2020–2022, szszss.
- License: MIT; the full text is retained in [`LICENSES/TpacTool-MIT.txt`](../LICENSES/TpacTool-MIT.txt).

| Implementation | Layout references |
| --- | --- |
| `core.py` | `AssetPackage.cs`, `AssetItem.cs`: package tables, assets and segments |
| `textures.py` | Texture metadata, format IDs and pixel-data layouts |
| `particles.py` | `ParticleEffectData.cs`: emitter records and curves |
| `mesh_encoding.py`, `mesh_validation.py`, `mesh_preview.py`, `models.py` | `Metamesh.cs`, `Mesh.cs`, `VertexStreamData.cs`, `Material.cs` |

Particle field meanings and packed tangent conventions include empirical mappings. Treat these as version-specific implementations rather than a complete official specification. When adding a format variant, document its field order and supported versions, add bounded reads and synthetic tests, and preserve fields that are not understood.

Asset type, shader and dependency GUIDs identify resources or layout conventions. A reference to an installed-game shader does not include its implementation. The built-in examples generate original textures, geometry and emitter data without requiring game files.

The container layer can copy unknown records without decoding them. This preserves stored bytes but does not establish that all dependencies or engine semantics are understood. Read [format support](formats.md) and [validation](validation.md) before extending the codecs.

Retain copyright notices when adapting upstream code. Record the upstream URL, revision, license and affected modules for new references. Dependency licenses are listed in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

# Format support and limits

## Containers

Reads TPAC container versions 1/2; writes version 2. Records preserve type GUID, asset GUID/name/version, metadata, dependencies, checksum and segment owner/type/version/flags. Stored payload bytes and storage modes are preserved when unchanged, including unknown segment types. Offsets and package-level layout are regenerated. Repacked files need not be byte-identical as a whole; record fingerprints are compared after writing.

Supported decoding includes raw and LZ4 payloads. Unknown storage methods remain opaque. Counts, table sizes, offsets and decoded sizes are bounded. Package tables are limited to 128 MiB, general counts to 100,000, individual decoded payloads to 256 MiB, and strings to 1 MiB. These are implementation limits rather than format specifications. Large payload copying/hashing is streamed in 1 MiB chunks; metadata and explicit previews are in memory.

Known-reference scanning is limited to 64 MiB per plan and reports truncation; large libraries use a byte-index scan instead of pairwise asset comparisons.

The tool does not rewrite XML references, remap colliding identities, update the game's resource database or automatically produce a dedicated-server companion package. Native dependency/shader identities can reference the user's installed game; no shader implementation is included.

## Textures

The preview supports the first mip of supported 2D RGBA/BGRA/R8 and BC1/2/3/5/7 records. Arrays, volumes, external streamed tiles and other layout variants can be preserved but may not preview. Images are bounded to 8192 pixels per dimension and 16 million pixels. Imports create uncompressed RGBA mip chains; texture compression, normal-map conversion and streaming-tile authoring are not included.

## Static geometry

Preview reads supported mesh metadata and position/UV/normal channels. It shows the lowest-numbered LOD and simple albedo lighting. This is not a PBR renderer. Source import creates LOD 0 geometry with a constant base-colour material for each group. JSON accepts:

```json
{
  "groups": [{
    "vertices": [
      [0,0,0, 0,0,1, 1,0,0, 1, 0,0],
      [1,0,0, 0,0,1, 1,0,0, 1, 1,0],
      [0,1,0, 0,0,1, 1,0,0, 1, 0,1]
    ],
    "indices": [0,1,2],
    "color": [0.2,0.7,0.6,1]
  }]
}
```

Each vertex contains position XYZ, normal XYZ, tangent XYZ, handedness and UV. Positions use metres; inputs should supply normalized orthogonal normal/tangent vectors, handedness ±1 and intended UVs. The importer rejects nonfinite data, zero normal/tangent vectors, out-of-range indices and oversized groups. It does not repair arbitrary tangent bases. Groups are bounded to 500,000 vertices / 1.5 million indices each and 1,024 groups; JSON input is limited to 128 MiB.

The optional Blender bridge applies object transforms and triangulates mesh loops. It imports static geometry only and rejects armature modifiers and vertex groups. It does not bake arbitrary modifiers or preserve texture networks, rigs or animation. Validate dimensions/orientation after import.

## Particles

The supported traversal is runtime segment version 1, emitter versions 0–2, with exact tail consumption. The four editable meanings are empirical mappings, not an official engine contract. Edits patch specific values while retaining other bytes. Unsupported variants fail and remain eligible for opaque copying.

Preview samples basic emission/lifetime/velocity/tint/alpha and available sprite textures. Unsupported shaders, blend modes, collision, drag, rotation, noise, full curves, attachments and audio are not reproduced. Fallback sprites and the built-in synthetic emitter are preview/test aids. New arbitrary particle authoring is available only through low-level code/extensions; the GUI edits existing supported records.

## Animations

Animation records can be inspected as container records and copied unchanged. Skeletal decoding, FBX animation import, playback, character preview and animation writing are not supported in 1.0.0. To preserve an animation, include its existing record and available dependencies in a build plan.

## Workspace format

A version-1 `.tpstudio` is a ZIP containing `workspace.json` and, when nonempty, `contents.tpac`. It is self-contained. Readers reject unexpected entries and limit metadata to 16 MiB and the embedded package to 8 GiB. Origins/protected source paths remain local metadata; do not publish real workspaces without reviewing those paths and asset rights. Session undo and live GUI state are not serialized. Only workspace format version 1 is supported; other layouts require exporting TPACs or supported source assets first.

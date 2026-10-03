# Desktop guide

## Open and inspect

Start `tpac-studio-gui`. **Examples** constructs an original checker texture, triangle/material and synthetic emitter. These fixtures demonstrate the tool without game files; the emitter is not an engine-tested effect.

**Open TPACs** accepts multiple packages; you can also drop `.tpac` files onto the window. Search by name and filter by type or source. A row's checkbox controls build inclusion; selecting the row controls preview. **Asset details** shows the structured API result, including decoder errors. Unknown records remain available for inspection and opaque repackaging.

Identical GUID/content records are deduplicated. Conflicting content is not silently renamed. When asked, choose:

| Policy | Behavior |
| --- | --- |
| `error` | Cancel the entire add operation if a conflict exists. |
| `keep` | Keep the existing workspace version. |
| `replace` | Replace matching GUIDs explicitly; a same-name/different-GUID collision still fails. |

Inspect the resulting assets after resolving conflicts. Rewriting every possible reference to a renamed GUID is outside this release's scope, so there is no automatic GUID remapping.

## Preview controls

Left drag orbits; right drag pans; the mouse wheel changes distance. Preview FOV changes the preview camera only. Static meshes use an approximate albedo/lighting display. Open referenced material and texture packages together for a more complete view.

Particle **Play** and the timeline cover six seconds. Scrubbing is deterministic. Supported material albedo sprites/flipbooks are used when available; otherwise the preview draws a procedural radial sprite. It approximates emission, velocity, tint and alpha. It does not reproduce native shaders, collision, lighting, turbulence, sound or every curve. A white circle in an effect with no material is the preview fallback, not a claim about how the effect looks in-game.

**Save preview PNG** writes the current viewport. It is a screenshot, not an asset export.

## Edit particles

Select a supported particle record, set multipliers, then press **Apply particle settings**. Values are relative to the **current** values: applying opacity `0.5` twice yields one quarter of the previous opacity. A value of `1` leaves that field unchanged. Supported range is `0.05`–`5`. The desktop applies to all emitters; the API can target one emitter index. Unsupported layouts fail instead of guessing.

**Undo** reverses up to 30 session edits. It does not undo a TPAC already written to disk. Undo history is not stored in saved workspaces.

## Import original assets

**Import** accepts supported images and static model inputs. Choose a unique alphanumeric/underscore asset name (up to 128 characters). Image imports generate full RGBA mipmaps. Model imports create geometry plus constant base-colour materials/textures. They do not copy source texture graphs, preserve skinning, author collision, or generate LODs.

Geometry JSON imports require no Blender. OBJ, FBX, glTF/GLB and BLEND use an explicitly selected local Blender executable. Import is background-only, disables automatic Python execution, has a five-minute timeout and rejects skinned geometry. Treat model files as trusted inputs to Blender; its importers are not a security sandbox.

## Save and build

**Save workspace** writes a self-contained `.tpstudio` file. It includes package contents, selections, origins and preview settings, so the original files are not needed merely to reopen it. It also retains source-protection records. Opening a workspace replaces the current session after an unsaved-work prompt.

**Build TPAC** first calculates a content-bound plan. With dependencies enabled it includes references discoverable among known assets. Review `missing_known_references` and `dependency_analysis`. An empty missing list does **not** mean all dependencies are resolved: unopened native packages, XML references and unknown payload relationships can be absent from the analysis.

Choose a new filename in a staging directory. Do not delete old packages until you have tested the replacements, checked module references, and made your own backups. TPAC Studio does not install files into the game or delete originals.

**Export current asset** creates a one-record TPAC or, for supported textures, a PNG. A one-record TPAC does not include dependencies; use the build workflow to assemble related assets.

## Recovery and compatibility

- `SOURCE_CHANGED`: an input changed since it was loaded. Reopen the source and review a new plan.
- `STALE_PLAN` / `STALE_REVISION`: inspect current state and redo the intended edit or plan; do not blindly retry old edits.
- `STALE_WORKSPACE`: another session saved the project. Save to a new path or reopen after preserving your changes.
- `WORKSPACE_BUSY`: another process owns a `.lock` file. If a process crashed, verify no writer is running before manually removing its stale lock.
- `PROTECTED_SOURCE`: pick a different output. Explicit overwrite does not disable source protection.
- Unsupported preview: keep the record opaque or install a trusted extension; no decoder means no preview.

TPAC Studio 1.0.0 reads version-1 `.tpstudio` workspaces. Other workspace layouts are rejected with `UNSUPPORTED`. To import data from another tool, open its TPAC packages or supported source assets in a new workspace.

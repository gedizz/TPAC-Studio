# Python and JSON API

All frontends call `tpac_studio.service.Studio`. Importing it does not import Qt or OpenGL. The public automation surface is the service; the versioned service contract is the supported integration boundary. Lower-level binary codec helpers are implementation details.

## Direct Python calls

```python
from tpac_studio.service import Studio
from tpac_studio.errors import StudioError

studio = Studio(root="./user-data")
try:
    studio.package_add(["first.tpac", "second.tpac"], conflict="error")
    records = studio.asset_list(kind="Particle", limit=100)
    print(records)
    state = studio.workspace_info()
    # Use an exact name or GUID discovered in the listing:
    # studio.particle_edit("my_effect", {"opacity": 0.8},
    #                      expected_revision=state["revision"])
    plan = studio.build_plan(include_dependencies=True)
    if plan["missing_known_references"]:
        raise RuntimeError("Review missing references before proceeding")
    report = studio.build_execute("merged.tpac", plan["plan_id"])
    studio.workspace_save("merged.tpstudio")
    print(report)
except StudioError as error:
    print(error.as_dict())
finally:
    studio.close()
```

Direct methods raise exceptions; `execute(operation, arguments)` validates a JSON request and returns a stable envelope. Use `execute` when you need a serialized thread-safe session. Direct method calls require caller serialization. Always close sessions opened from saved workspaces to release temporary backing files.

## Structured results

```json
{
  "api_version": "1",
  "request_id": "caller-id-or-generated-uuid",
  "ok": true,
  "revision": 1,
  "result": {},
  "warnings": []
}
```

Operation errors replace `result` with `error: {code, message, details}` and set `ok` to false. CLI bootstrap/argument errors can omit `request_id` and `revision`. Parser usage errors use argparse's stderr and exit 2. JSON operation output uses stdout; diagnostics must not be written there. Success exits 0; operation failure exits 2. JSON numbers must be finite, unknown argument keys fail, and schemas reject strings in numeric or boolean fields.

`schemas` discovers operation arguments and editable fields; [api-reference.md](api-reference.md) lists every operation and is generated from the same contracts. `src/tpac_studio/schemas/operations.json` is a machine-readable snapshot. API major version is `1`; app version is separate.

## CLI

PowerShell, after installation:

```powershell
tpac-studio capabilities --json
tpac-studio examples_load --workspace .\user-data\demo.tpstudio
$plan = tpac-studio build_plan --workspace .\user-data\demo.tpstudio | ConvertFrom-Json
if (-not $plan.ok) { throw $plan.error.message }
@{ output = '.\user-data\demo.tpac'; plan_id = $plan.result.plan_id } |
    ConvertTo-Json | Set-Content -Encoding utf8 .\user-data\build.json
tpac-studio build_execute --workspace .\user-data\demo.tpstudio --request .\user-data\build.json
```

For Windows PowerShell 5.1, save request JSON as UTF-8 without a BOM or use a Python script to write it; UTF-8 BOM requests are also accepted. `--request` holds the arguments object, not an envelope. `--args` accepts the same object inline when shell quoting is convenient.

Each CLI invocation is a separate process. `--workspace` loads an existing project and automatically saves successful asset/selection/settings mutations. Undo history is session-local and cannot span separate CLI calls; use Python, MCP or the GUI for multi-step undo. Without `--workspace`, state disappears on process exit unless the requested operation explicitly saves/builds an output.

With `--root`, relative paths (including `--workspace` and `--request`) are relative to that root. Absolute resolved paths outside it fail. The root boundary is an operational guard, not an OS sandbox against hostile local processes, filesystem races or trusted extension code.

## Revisions and building

Mutations increment the workspace revision. Supply `expected_revision` from a fresh read to reject stale edits. Undo increments the revision too. `build_plan` hashes the selected assets, content fingerprints, dependency choices and revision. `build_execute` recomputes the plan; changing the workspace or input files invalidates the old plan.

`include_dependencies` must match the plan. `allow_missing=true` is an explicit override for known missing references only. It does not certify hidden dependencies. `overwrite=false` is the default. Even `overwrite=true` cannot replace source TPAC paths or hardlinks to them.

Builds are synchronous. There is no job cancellation API, streaming progress protocol or automatic game installation. A temporary output is read back and verified before a final single-file commit. By default the exclusive commit uses a hardlink: use NTFS or another filesystem supporting hardlinks; unsupported filesystems report an I/O failure. Explicit replacement uses atomic rename where supported. This is not a multi-output transaction.

## Imports and settings

`texture_import(path, name)` accepts supported Pillow image inputs and authors RGBA mipmaps. `model_import(path, name, scale)` accepts the JSON layout in [formats.md](formats.md), or uses the host-configured `Studio(blender=...)` executable. Paths/executable choice are never interpolated into shell code.

`particle_edit(asset, values, emitter=None)` applies multipliers to all emitters or one zero-based index. Fields: `opacity`, `size`, `emission`, `lifetime`, each 0.05–5. Repeated edits compound. Lifetime edits also adjust sprite playback rate inversely. Unrecognized layout versions are rejected.

`settings_update` stores preview-only fields `preview.fov`, `preview.loop` and `preview.emitter_speed`; their ranges/defaults come from `schemas`. These do not change the game's camera, effects or options.

## Error codes

Common codes are `INVALID_ARGUMENT`, `NOT_FOUND`, `UNSUPPORTED`, `RESOURCE_LIMIT`, `CONFLICT`, `SOURCE_CHANGED`, `PROTECTED_SOURCE`, `OUTPUT_EXISTS`, `STALE_REVISION`, `STALE_PLAN`, `MISSING_DEPENDENCIES`, `STALE_WORKSPACE`, `WORKSPACE_BUSY`, `PATH_OUTSIDE_ROOT`, `DEPENDENCY_MISSING`, `IMPORT_FAILED`, `IO_ERROR` and `INTERNAL_ERROR`. Treat messages as diagnostics, not stable strings for branching. Inspect the code and details; never retry a mutation without checking whether it committed.

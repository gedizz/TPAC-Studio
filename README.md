# TPAC Studio

**Inspect, organize and rebuild TPAC packages through a desktop application, Python, JSON CLI or MCP.**

TPAC Studio is an independent community tool by **X7 Dragon**. This is the **0.2.0 source release candidate**, prepared for private review. It is not affiliated with or endorsed by TaleWorlds Entertainment.

![TPAC Studio showing an original procedural model](docs/images/studio.png)

## What works

| Task | Support in this release |
| --- | --- |
| Open and browse packages | TPAC container versions 1 and 2; names, types, GUIDs, segments and source packages |
| Merge and remove assets | Workspace selection, explicit conflict policies, session undo and reviewed build plans |
| Preserve unfamiliar records | Opaque metadata and stored segments, including animation records, can be repackaged without decoding |
| Texture preview/import | Supported 2D formats; image import creates RGBA mipmaps; PNG export |
| Static model preview/import | Supported mesh layouts; geometry JSON, plus optional Blender for OBJ/FBX/glTF/BLEND |
| Particle preview/edit | Approximate sprite playback and scrubbing; opacity, size, emission and lifetime multipliers for supported layouts |
| Save work | Self-contained `.tpstudio` workspaces, with concurrent-save detection |
| Automate | Shared Python service, structured JSON CLI, local stdio MCP and opt-in Python extensions |

**Limits:** this is not the game renderer. Dependency discovery is incomplete; structural verification is not an engine compatibility certificate. Animation playback, character preview, rigging and animation authoring are **not included**: the earlier prototype's animation implementation and character assets are held pending provenance resolution. Static model import currently uses constant base colours, not full material graphs. See [supported formats](docs/formats.md), [validation](docs/validation.md) and [provenance](docs/provenance.md) before distribution or production use.

## Install and launch

Tested on Windows with Python 3.12, Qt 6.11 and Blender 5.1. Python **3.12+** is required. Blender is optional; no game installation is required to start the application or run the original examples.

From this repository folder in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install ".[gui,mcp]"
.\.venv\Scripts\tpac-studio-gui.exe
```

For a headless install use `python -m pip install .`. On other platforms the Python API and CLI are intended to be portable, but the desktop application has only been validated on Windows. The GUI requires a functioning OpenGL compatibility context.

The [build guide](docs/building.md) explains development installs, tests, executable generation and pinned dependency snapshots. This repository contains source rather than bundled executables or third-party runtime binaries.

## First package

1. Click **Examples** to load original procedural data, or **Open TPACs** to load your packages.
2. Select a row to inspect it. Use the checkboxes to choose the assets to build; **Remove** removes a workspace record.
3. Save a workspace if you want to resume later.
4. Click **Build TPAC**, review the asset list and dependency warnings, and choose a **new output filename**.

The writer verifies the output's stored records before publishing it. It refuses to overwrite original package inputs, even when overwrite is explicitly enabled. Source packages are never deleted by this application. Repackaging does not automatically update module XML, game references or other packages.

## Python

```python
from tpac_studio.service import Studio

studio = Studio(root="./user-data")
try:
    studio.examples_load()
    plan = studio.build_plan()
    print(studio.build_execute("example.tpac", plan["plan_id"]))
finally:
    studio.close()
```

The exact example is available as [examples/build_demo.py](examples/build_demo.py). Read the [Python and JSON API guide](docs/api.md) for error envelopes, revisions, imports, selection and safe builds.

## Use with AI

Launch `tpac-studio-mcp --root <your-asset-folder>` from an MCP-capable host, or have your agent call the JSON CLI. The host should call `capabilities` and `schemas`, inspect inputs, make explicit edits, review `build_plan`, then call `build_execute` with that plan's ID. Read the [AI setup and workflow guide](docs/ai.md) for a complete MCP configuration and prompts.

The MCP server uses local stdio, has no listening network port, and owns a separate workspace. It does not attach to an open GUI or silently change the GUI's unsaved work. Save/reopen a workspace to exchange work between them.

## Documentation

- [Desktop guide](docs/user-guide.md): browsing, merge conflicts, previews, imports and rebuilding.
- [Python / JSON API](docs/api.md) and [generated operation reference](docs/api-reference.md).
- [AI / MCP guide](docs/ai.md): setup, schemas, recipes and session boundaries.
- [Extensions](docs/extensions.md): versioned provider contract and runnable example.
- [Formats and limitations](docs/formats.md).
- [Directory and architecture map](docs/architecture.md).
- [Build and release guide](docs/building.md).
- [Provenance and release gates](docs/provenance.md), [third-party notices](THIRD_PARTY_NOTICES.md), [validation](docs/validation.md).
- [Contributing](CONTRIBUTING.md), [security](SECURITY.md) and [agent instructions](AGENTS.md).

## License

Original eligible code and documentation: **MIT**, copyright **2026 X7 Dragon**. Adapted TpacTool format work retains its MIT attribution and license. Dependencies retain their own licenses. See [LICENSE](LICENSE), [NOTICE](NOTICE) and [LICENSES](LICENSES/README.md).

This license does not grant rights to TaleWorlds software, game assets, third-party mods or packages you open. The provenance review is documented, not a legal clearance or a clean-room certification. Public distribution remains a separate decision from preparing this source folder.

# Build, test and release

## Development environment

Tested on Windows using Python 3.12.14. From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[gui,mcp,dev]"
.\.venv\Scripts\python.exe -m ruff check src tests tools examples
.\.venv\Scripts\python.exe -m ruff format --check src tests tools examples
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools/generate_reference.py --check
```

`requirements-lock.txt` records the exact tested environment. To constrain the declared dependencies to those versions, add `-c requirements-lock.txt` to pip install. It is a Windows snapshot, not a hash-locked or cross-platform reproducibility guarantee. Core, GUI, MCP and developer dependencies are separated through package extras. The tests currently require the development, GUI and MCP extras (mesh decoding tests use NumPy); no game files are used.

Generate schemas after changing public signatures: `python tools/generate_reference.py`. Run the original workflow with `python examples/build_demo.py --output local/demo`.

The CI workflow repeats source checks and packaging on Windows/Python 3.12. Desktop rendering is a separate manual check: `python tools/check_gui.py --output local/gui-check`. It opens only this application and records example screenshots, GL validity and decoder errors. It does not launch or automate the game. See [validation.md](validation.md) for what was actually run.

## Python distributions

```powershell
python -m build
python -m pip install --force-reinstall --no-deps .\dist\tpac_studio-0.2.0-py3-none-any.whl
```

Review wheel/sdist contents before publishing: include licenses, source and intended docs; exclude environments, user assets, logs, game files and research dumps. Neither command uploads to PyPI or GitHub.

## Local Windows executable

```powershell
python -m pip install ".[gui,bundle]"
python tools/build_executable.py
.\dist\TPACStudio\TPACStudio.exe
```

PyInstaller creates a **directory**, not a standalone single file. Keep the whole directory together. The helper does not sign the executable or create an installer. The source release's executable helper is supplied for local development; consult the validation report for whether it was run for this candidate. The Python package entry points remain the supported CLI/MCP distribution.

For a short packaged-app check, run `TPACStudio.exe --check-startup --output <new-test-folder>`. It opens its own example window briefly, saves original-example screenshots/results, then exits. The check never launches the game. The build helper constrains only its child PATH to avoid collecting unrelated host DLLs with colliding names.

Qt/PySide is dynamically linked in a normal bundle and carries LGPL/GPL terms distinct from this project's MIT license. Before redistributing binaries, preserve dependency notices, include required license texts, provide required source/relinking/replacement information as applicable, and review the precise components packaged by PyInstaller. The helper alone does not satisfy or certify all binary-distribution obligations. Keep source available and do not label all bundled libraries MIT.

Blender is external, optional and never bundled. If importing through Blender from a frozen GUI, ensure the installed Blender can load its own native libraries; the importer temporarily removes PyInstaller's Windows DLL search override around child creation. A known-good source-based launch is useful for diagnosing native dependency issues.

## Preparing the GitHub folder

This delivered folder is the repository root. It includes no Git history or remote, so the owner can upload/import it into a new private repository. `.gitignore` covers generated binaries, packages, workspaces, caches and secrets; it does not remove already tracked files and does not prevent accidental manual web uploads. Review the actual file list.

Before a public release: resolve [provenance gates](provenance.md), confirm animation scope, set a security contact/private reporting channel, select supported platforms and publish test coverage honestly. Enable branch protection. Never push directly to main/master or create/merge a PR on the owner's behalf without explicit delegation.

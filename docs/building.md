# Build, test and release

## Development environment

From the repository root on Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[gui,mcp,dev]"
.\.venv\Scripts\python.exe -m ruff check src tests tools examples
.\.venv\Scripts\python.exe -m ruff format --check src tests tools examples
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools/generate_reference.py --check
```

`requirements-lock.txt` records tested dependency versions. Add `-c requirements-lock.txt` to pip install to constrain dependencies to that snapshot. Core, GUI, MCP and developer dependencies are separated through extras. Tests use the GUI and MCP dependencies but no game files.

After changing public signatures, run `python tools/generate_reference.py` to update the API documentation and JSON schemas. Run `python examples/build_demo.py --output local/demo` to build an original example package and workspace.

## Python package

```powershell
python -m build
python -m pip install --force-reinstall --no-deps .\dist\tpac_studio-1.0.0-py3-none-any.whl
```

The wheel includes the core package and entry points. Install the appropriate optional dependencies for GUI or MCP use. Review archive contents before distribution; exclude environments, user assets, logs and generated build directories.

## Windows application

```powershell
python -m pip install ".[gui,bundle]"
python tools/build_executable.py
.\dist\TPACStudio\TPACStudio.exe
```

The build creates a directory containing `TPACStudio.exe` and `_internal`. Distribute the whole directory as a ZIP; the executable depends on those runtime files. The build helper constrains only its child PATH to avoid collecting incompatible DLLs from unrelated native tools. The application is not code-signed by this script.

Run `TPACStudio.exe --check-startup --output <new-test-folder>` for a packaged-app check. It opens original examples, saves screenshots/results and exits. It never launches the game. Run the check on an extracted release ZIP as well as the build directory.

Blender is optional and external. The frozen application's importer temporarily clears PyInstaller's Windows DLL-search override while spawning Blender so the child can load its own libraries.

## Dependency notices

Include the application license, `NOTICE` and relevant third-party license texts in binary archives. Qt/PySide libraries use LGPL/GPL licensing options distinct from the application's MIT license. Keep dynamically loaded libraries replaceable, provide matching source/build references and retain their notices. See [Qt licensing](https://doc.qt.io/qt-6/licensing.html) and [third-party notices](../THIRD_PARTY_NOTICES.md) for component references.

## Release checklist

1. Select a clean committed revision and set the package/app version consistently.
2. Run automated checks and build the wheel and Windows application from that revision.
3. Include documentation, licenses, source/build information and original examples.
4. Extract the Windows ZIP into a fresh directory and run the packaged-app check.
5. Generate SHA-256 checksums for the final artifacts.
6. Create the version tag at the tested commit and attach the archives, wheel and checksums to the GitHub release.

Keep release binaries as release attachments rather than committing them to Git. `.gitignore` excludes generated packages, workspaces, binaries and caches; inspect staged files before committing. Release notes should state supported features, installation steps and known limitations.

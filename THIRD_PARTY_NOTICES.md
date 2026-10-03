# Third-party notices

TPAC Studio's MIT license covers eligible original work. The licenses below remain with their respective authors. This source folder does not bundle the listed runtimes. Exact installed versions, metadata and license-file hashes from the tested environment are recorded in [docs/dependency-inventory.json](docs/dependency-inventory.json); missing license metadata is recorded as null.

| Component | Use / license reference |
| --- | --- |
| [TpacTool](https://github.com/szszss/TpacTool) | Adapted/referenced format layouts; MIT; full notice at `LICENSES/TpacTool-MIT.txt` and revision in `NOTICE` |
| [Python](https://docs.python.org/3/license.html) | External interpreter; PSF and included component licenses |
| [PySide6 / Shiboken / Qt](https://doc.qt.io/qtforpython-6/licenses.html) | Optional GUI; LGPL-3.0 / GPL alternatives and component-specific terms; not relicensed MIT |
| [PyOpenGL](https://github.com/mcfletch/pyopengl) | Optional OpenGL bindings; upstream BSD-style/OpenGL component notices |
| [NumPy](https://github.com/numpy/numpy) | Optional preview arrays; NumPy and wheel-bundled component notices |
| [python-lz4](https://github.com/python-lz4/python-lz4) | Compressed payload decode; BSD notices including bundled LZ4 |
| [Pillow](https://github.com/python-pillow/Pillow) | Image decode/encode; MIT-CMU and wheel-bundled component licenses |
| [jsonschema](https://github.com/python-jsonschema/jsonschema) | Input contracts; MIT and its dependency notices |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Optional stdio protocol adapter; MIT, plus transitive dependency licenses |
| [Blender](https://www.blender.org/about/license/) | Optional separate executable; GPL; neither Blender nor its Python runtime is bundled here |
| [PyInstaller](https://pyinstaller.org/en/stable/license.html) | Optional build tool; GPL with distribution exception; inspect its full terms before shipping binaries |
| pytest, Ruff, build, setuptools | Development/build tools; retain upstream licenses when redistributing their components |

Transitive dependencies are included in the inventory because the MCP SDK and GUI have dependencies of their own. Some package metadata omits a concise SPDX expression; the inventory lists shipped license files and metadata URLs where available. Consult each component's included license files when distributing a binary build.

Retain the TpacTool license and project notices in source distributions. Binary archives must also include the relevant runtime license texts and source/build references. Keep the Qt/PySide libraries replaceable and distinguish their licenses from the application's MIT license.

TaleWorlds game content and user-provided assets are not licensed by this project. No asset license is inferred from successful decoding or repackaging.

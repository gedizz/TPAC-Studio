"""Create a local one-directory GUI executable using an installed PyInstaller.

Run with the GUI and bundle dependencies installed. See docs/building.md for
packaging, license notices and verification instructions.
"""

import subprocess
import sys
import os
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    if sys.platform == "win32":
        # A host's unrelated native tools may ship incompatible DLLs named like
        # Windows libraries (notably ICU). Do not collect them from the host PATH.
        windows = Path(environment.get("SystemRoot", r"C:\Windows"))
        environment["PATH"] = os.pathsep.join(
            str(path)
            for path in (
                Path(sys.executable).parent,
                Path(sys.base_prefix),
                windows / "System32",
                windows,
            )
        )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--windowed",
            "--name",
            "TPACStudio",
            "--paths",
            str(root / "src"),
            "--collect-all",
            "OpenGL",
            "--collect-data",
            "tpac_studio",
            "--copy-metadata",
            "jsonschema",
            "--copy-metadata",
            "referencing",
            "--copy-metadata",
            "jsonschema-specifications",
            "--add-data",
            f"{root / 'src/tpac_studio/blender_import.py'}:tpac_studio",
            "--distpath",
            str(root / "dist"),
            "--workpath",
            str(root / "build/pyinstaller"),
            "--specpath",
            str(root / "build"),
            str(root / "tools/gui_entry.py"),
        ],
        check=True,
        cwd=root,
        env=environment,
    )


if __name__ == "__main__":
    main()

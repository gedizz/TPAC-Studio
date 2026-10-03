"""Author static mesh packages from documented geometry JSON or optional Blender."""

import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

from .core import Asset, Segment, TYPES, ZERO, guid, pack, string
from .errors import require
from .mesh_encoding import VERTICES, compact_group, mesh_record, vertex_stream
from .textures import safe_name, texture_from_image


def model_assets(document: dict, name: str, scale: float = 1.0) -> list[Asset]:
    """Create static records from groups of 12-float vertices and triangle indices.

    Vertex layout: position3, normal3, tangent3, handedness1, UV2. Inputs are bounded
    and must be finite; procedural materials become a constant base-colour texture.
    """
    safe_name(name)
    require(
        type(scale) in (int, float) and math.isfinite(scale) and 0.0001 <= scale <= 10000,
        "Invalid model scale",
        "INVALID_ARGUMENT",
    )
    groups = document.get("groups", [])
    require(
        isinstance(groups, list) and 0 < len(groups) <= 1024,
        "Expected 1–1024 geometry groups",
        "INVALID_ARGUMENT",
    )
    assets, prepared = [], []
    for index, group in enumerate(groups):
        vertices, indices = group.get("vertices", []), group.get("indices", [])
        require(
            0 < len(vertices) <= 500_000
            and 0 < len(indices) <= 1_500_000
            and len(indices) % 3 == 0,
            "Invalid geometry size",
            "RESOURCE_LIMIT",
        )
        require(
            all(
                len(v) == 12 and all(type(x) in (int, float) and math.isfinite(x) for x in v)
                for v in vertices
            ),
            "Vertices must contain 12 finite numbers",
            "INVALID_ARGUMENT",
        )
        require(
            all(type(i) is int and 0 <= i < len(vertices) for i in indices),
            "Invalid triangle index",
            "INVALID_ARGUMENT",
        )
        require(
            all(
                sum(x * x for x in v[3:6]) > 1e-12 and sum(x * x for x in v[6:9]) > 1e-12
                for v in vertices
            ),
            "Normals/tangents must be nonzero",
            "INVALID_ARGUMENT",
        )
        material = f"{name}_part{index}_material"
        color = group.get("color", [0.6, 0.7, 0.8, 1])
        require(
            len(color) == 4
            and all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1 for x in color),
            "Colour must be four values from zero to one",
            "INVALID_ARGUMENT",
        )
        texture = texture_from_image(
            Image.new("RGBA", (4, 4), tuple(round(x * 255) for x in color)),
            f"{name}_part{index}_albedo",
        )
        assets.append(texture)
        # Metadata field order follows TpacTool Material.cs. Native shader identity is
        # a reference to the user's game; its implementation is not distributed.
        meta = pack("I", 0) + ZERO.bytes_le + pack("III", 2, 0, 0) + pack("II", 0, 0)
        meta += (
            string("no_alpha_blend")
            + __import__("uuid").UUID("328d3572-5e9e-4183-b49e-f451a19213d0").bytes_le
            + pack("ii", 1, 0)
            + texture.id.bytes_le
        )
        meta += (
            pack("fI", 0, 0)
            + pack("4f", 1, 0.65, 1, 1)
            + pack("16f", *([0] * 8 + [1] * 8))
            + pack("i7f", 0, 0, 1, 1, 0, 0.5, 1, 1)
        )
        assets.append(Asset(material, TYPES["Material"], guid(material), meta))
        prepared.append(
            compact_group(
                {
                    "vertices": [
                        [x * scale if i < 3 else x for i, x in enumerate(v)] for v in vertices
                    ],
                    "indices": indices,
                    "material": material,
                    "lod": 0,
                }
            )
        )
    metadata = (
        pack("I", 1)
        + guid(prepared[0]["material"]).bytes_le
        + pack("f", 3.402823466e38)
        + string("")
        + ZERO.bytes_le
        + pack("IIi", 0, 0, len(prepared))
    )
    segments = []
    for index, group in enumerate(prepared):
        subname = f"{name}.lod0.part{index}"
        metadata += mesh_record(subname, group)
        segments.append(
            Segment(guid(subname), VERTICES, raw=vertex_stream(group["vertices"], group["indices"]))
        )
    metadata += ZERO.bytes_le + pack("i??", 0, True, True)
    assets.append(Asset(name, TYPES["Mesh"], guid(name), metadata, 1, tuple(segments)))
    return assets


def import_model(path: Path, name: str, scale: float, blender: str | None) -> list[Asset]:
    """Read bounded JSON or launch an explicitly configured Blender executable."""
    safe_name(name)
    if path.suffix.lower() == ".json":
        require(
            path.stat().st_size <= 128 * 1024**2, "Geometry JSON exceeds 128 MiB", "RESOURCE_LIMIT"
        )
        document = json.loads(path.read_text(encoding="utf8"))
    else:
        require(
            path.suffix.lower() in (".obj", ".fbx", ".glb", ".gltf", ".blend"),
            "Unsupported model input",
            "UNSUPPORTED",
        )
        require(
            blender is not None and Path(blender).is_file(),
            "The host must configure Blender for this import",
            "DEPENDENCY_MISSING",
        )
        with tempfile.TemporaryDirectory(prefix="tpac-blender-") as directory:
            job = Path(directory) / "job.json"
            result = Path(directory) / "result.json"
            job.write_text(
                json.dumps({"source": str(path), "output": str(result)}), encoding="utf8"
            )
            process = _run_blender(
                [
                    blender,
                    "--background",
                    "--factory-startup",
                    "--disable-autoexec",
                    "--python-exit-code",
                    "1",
                    "--python",
                    str(Path(__file__).with_name("blender_import.py")),
                    "--",
                    str(job),
                ],
                capture_output=True,
                text=True,
                encoding="utf8",
                errors="replace",
                timeout=300,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            require(
                process.returncode == 0 and result.is_file(),
                "Blender import failed",
                "IMPORT_FAILED",
                log=(process.stdout + process.stderr)[-4000:],
            )
            require(
                result.stat().st_size <= 128 * 1024**2,
                "Imported geometry exceeds 128 MiB",
                "RESOURCE_LIMIT",
            )
            document = json.loads(result.read_text(encoding="utf8"))
    return model_assets(document, name, scale)


def _run_blender(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Keep a frozen Windows parent's bundled DLLs out of the external Blender process."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return subprocess.run(command, **kwargs)
    import ctypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
    kernel.SetDllDirectoryW.restype = ctypes.c_int
    kernel.GetDllDirectoryW.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p]
    kernel.GetDllDirectoryW.restype = ctypes.c_uint32
    length = kernel.GetDllDirectoryW(0, None)
    previous = ctypes.create_unicode_buffer(length + 1)
    kernel.GetDllDirectoryW(len(previous), previous)
    require(bool(kernel.SetDllDirectoryW(None)), "Could not reset DLL search path", "IMPORT_FAILED")
    environment = dict(os.environ)
    bundle = str(getattr(sys, "_MEIPASS", ""))
    if bundle:
        environment["PATH"] = os.pathsep.join(
            part
            for part in environment.get("PATH", "").split(os.pathsep)
            if not str(Path(part).resolve()).casefold().startswith(bundle.casefold() + os.sep)
            and str(Path(part).resolve()).casefold() != bundle.casefold()
        )
    try:
        # Spawn while the parent override is clear; restore it before waiting.
        kwargs.pop("capture_output", None)
        timeout = kwargs.pop("timeout", None)
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment, **kwargs
        )
    finally:
        kernel.SetDllDirectoryW(previous.value or None)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)

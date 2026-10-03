"""Supported static mesh/material preview layouts from MIT TpacTool.

This is a format decoder, not a game renderer; unknown variants fail explicitly.
"""

from .core import Reader
from .core import Asset
import numpy as np


def material_info(a: Asset) -> dict:
    """Read the supported material slot map and preview-relevant flags."""
    r = Reader(a.metadata)
    r.n("I")
    r.take(16)
    r.n("II")
    flags = r.ss()
    r.n("I")
    r.ss()
    blend = r.s()
    shader = r.guid()
    n = r.n("i")
    if not 0 <= n < 64:
        raise ValueError("Unsupported material slots")
    slots = {}
    for _ in range(n):
        slot = r.n("i")
        slots[slot] = r.guid()
    r.n("f")
    flags += r.ss()
    return {"slots": slots, "flags": flags, "blend": blend, "shader": shader}


def mesh_parts(a: Asset) -> list[dict]:
    """Read static submesh arrays; reject invalid stream bounds or indices."""
    r = Reader(a.metadata)
    version = r.n("I")
    r.take(16)
    r.n("f")
    r.s()
    r.take(16)
    if version >= 1:
        _, cloth = r.n("II")
        if cloth:
            r.s()
    count = r.n("i")
    if not 0 <= count <= 10000:
        raise ValueError("Unsupported mesh metadata")
    result = []
    for _ in range(count):
        _, lod, ver = r.n("?iI")
        r.take(16)
        r.n("I")
        owner = r.guid()
        name = r.s()
        r.n("I")
        r.ss()
        mat = r.guid()
        r.take(64)
        key_count, pos_count, face_count, vc, skin_count, _ = r.n("6i")
        r.take(52)
        r.n("i")
        r.ss()
        r.n("f")
        r.s()
        r.take(36)
        r.n("i??ff?")
        s = next(
            (
                s
                for s in a.segments
                if s.owner == owner and str(s.kind) == "bb1df897-584f-4770-abf2-663fe449f247"
            ),
            None,
        )
        if not s:
            continue
        raw = s.data()
        v = Reader(raw)
        ni = v.n("I")
        idx = np.frombuffer(
            v.take(ni * (4 if vc >= 65535 else 2)), dtype="<u4" if vc >= 65535 else "<u2"
        ).astype(np.uint32)
        table = v.position
        channels = [v.n("QQ") for _ in range(14 if a.version >= 1 else 13)]

        def channel(n, dtype, components):
            off, size = channels[n]
            if not size:
                return None
            if table + off + size > len(raw):
                raise ValueError("Vertex stream out of bounds")
            arr = np.frombuffer(raw[table + off : table + off + size], dtype=dtype)
            return arr.reshape(-1, components).copy()

        pos = channel(4, "<f4", 3)
        if pos is None:
            pos = channel(11, "<f2", 4)[:, :3].astype(np.float32)
        normal = channel(6, "<f4", 3)
        uv = channel(2, "<f4", 2)
        if normal is None:
            normal = np.tile([0, 0, 1], (len(pos), 1)).astype(np.float32)
        if uv is None:
            uv = np.zeros((len(pos), 2), np.float32)
        if len(idx) and idx.max() >= len(pos):
            raise ValueError("Invalid vertex index")
        result.append(
            dict(name=name, lod=lod, material=mat, pos=pos, normal=normal, uv=uv, indices=idx)
        )
    return result

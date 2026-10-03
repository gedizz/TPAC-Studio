"""Static mesh serialization helpers. Layout references: MIT TpacTool Model/
Metamesh.cs, Mesh.cs, VertexStreamData.cs. See docs/format-references.md.
Packed tangent conventions are empirical format mappings. Validate new variants
with explicit stream-layout and tangent-basis checks.
"""

import math
import uuid
from .core import guid, pack, string, ZERO
from .mesh_validation import validate_stream


def strings(values: list[str]) -> bytes:
    """Encode the counted string-list convention used by mesh metadata."""
    return pack("I", len(values)) + b"".join(string(v) for v in values)


METAMESH = uuid.UUID("a08f8b97-197c-4bea-b95b-53846cae834e")
VERTICES = uuid.UUID("bb1df897-584f-4770-abf2-663fe449f247")


def tangent_quaternion(v: list[float]) -> bytes:
    """Encode a signed four-short tangent basis from a complete source vertex."""
    # Native QTangent axes are normal, tangent, cross(normal,tangent).
    # The sign of W stores the opposite of the tangent's handedness.
    n = v[3:6]
    t = v[6:9]
    b = (n[1] * t[2] - n[2] * t[1], n[2] * t[0] - n[0] * t[2], n[0] * t[1] - n[1] * t[0])
    m = [[n[i], t[i], b[i]] for i in range(3)]
    trace = m[0][0] + m[1][1] + m[2][2]
    if trace > 0:
        s = math.sqrt(trace + 1) * 2
        q = [(m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s, s / 4]
    else:
        i = max(range(3), key=lambda j: m[j][j])
        j = (i + 1) % 3
        k = (i + 2) % 3
        s = math.sqrt(max(0, 1 + m[i][i] - m[j][j] - m[k][k])) * 2
        if s < 1e-8:
            raise ValueError("Degenerate tangent basis")
        q = [0, 0, 0, 0]
        q[i] = s / 4
        q[j] = (m[i][j] + m[j][i]) / s
        q[k] = (m[i][k] + m[k][i]) / s
        q[3] = (m[k][j] - m[j][k]) / s
    length = math.sqrt(sum(x * x for x in q))
    q = [x / length for x in q]
    if (q[3] < 0) != (v[9] > 0):
        q = [-x for x in q]
    # Keep the sign bit representable at exact 180-degree rotations.
    if abs(q[3]) < 1 / 32767:
        q[3] = (-1 if v[9] > 0 else 1) / 32767
    return pack("4h", *(max(-32767, min(32767, round(x * 32767))) for x in q))


def packed_direction(v: list[float], tangent: bool = False) -> bytes:
    """Encode the supported packed normal or tangent stream element."""
    bits = (10, 11, 10) if tangent else (11, 11, 10)
    parts = [round((max(-1, min(1, x)) + 1) * 0.5 * ((1 << b) - 1)) for x, b in zip(v, bits)]
    value = (parts[0] << (bits[1] + bits[2])) | (parts[1] << bits[2]) | parts[2]
    if tangent and v[3] < 0:
        value |= 1 << 31
    return pack("I", value)


def vertex_stream(vertices: list[list[float]], indices: list[int]) -> bytes:
    """Write all fourteen version-1 channels and verify their offsets/strides."""
    # Version 1 has fourteen descriptors. Offsets include this table itself;
    # TpacTool's sequential reader ignores offsets, whereas the engine uses them.
    channels = [b""] * 14
    channels[0] = bytes([255, 255, 255, 255]) * len(vertices)
    channels[1] = channels[0]
    channels[2] = b"".join(pack("2f", *v[10:12]) for v in vertices)
    channels[3] = channels[2]
    channels[4] = b"".join(pack("3f", *v[:3]) for v in vertices)
    channels[5] = channels[4]
    channels[6] = b"".join(pack("3f", *v[3:6]) for v in vertices)
    channels[7] = b"".join(pack("4f", *v[6:10]) for v in vertices)
    channels[8] = bytes(4 * len(vertices))
    channels[9] = bytes(4 * len(vertices))
    channels[10] = b"".join(packed_direction(v[3:6]) for v in vertices)
    channels[11] = b"".join(pack("4e", *v[:3], 1) for v in vertices)
    channels[12] = b"".join(packed_direction(v[6:10], tangent=True) for v in vertices)
    channels[13] = b"".join(tangent_quaternion(v) for v in vertices)
    result = pack("i", len(indices)) + pack(
        ("I" if len(vertices) >= 65535 else "H") * len(indices), *indices
    )
    offset = len(channels) * 16
    for channel in channels:
        result += pack("QQ", offset, len(channel))
        offset += len(channel)
    data = result + b"".join(channels)
    validate_stream(data, len(vertices), version=1, require_complete=True)
    return data


def compact_group(group: dict) -> dict:
    """Deduplicate complete vertices while retaining UV and normal seams."""
    # Share only identical complete vertices: UV and normal seams remain intact.
    vertices = []
    lookup = {}
    indices = []
    for old_index in group["indices"]:
        vertex = tuple(group["vertices"][old_index])
        if vertex not in lookup:
            lookup[vertex] = len(vertices)
            vertices.append(vertex)
        indices.append(lookup[vertex])
    return dict(group, vertices=vertices, indices=indices)


def mesh_record(name: str, group: dict) -> bytes:
    """Write supported submesh metadata with computed bounds and material identity."""
    vertices = group["vertices"]
    count = len(vertices)
    lo = [min(v[i] for v in vertices) for i in range(3)]
    hi = [max(v[i] for v in vertices) for i in range(3)]
    center = [(a + b) / 2 for a, b in zip(lo, hi)]
    radius = max(math.dist(v[:3], center) for v in vertices)
    meta = (
        pack("?iI", True, group["lod"], 2)
        + ZERO.bytes_le
        + pack("I", 1)
        + guid(name).bytes_le
        + string(name)
    )
    meta += pack("I", 0) + strings([]) + guid(group["material"]).bytes_le
    meta += pack("16f", *([1] * 8 + [0] * 8))
    meta += pack("6i", 0, count, len(group["indices"]) // 3, count, 0, 0)
    meta += pack("13f", *(lo + [1] + hi + [1] + center + [1] + [radius]))
    meta += pack("i", 0) + strings([]) + pack("f", 1) + string("") + pack("9f", *([0] * 9))
    meta += pack("i??ff?", 120, False, False, -1, 1, False)
    return meta

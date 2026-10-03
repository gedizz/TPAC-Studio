"""Validate TPAC vertex descriptors by their offsets, as the engine does.

Use with TpacTool-independent meshes exported by this builder, before writing
the container. This also accepts raw native streams for format comparisons.
"""

import struct

STRIDES = (4, 4, 8, 8, 12, 12, 12, 16, 4, 4, 4, 8, 4, 8)


def validate_stream(data, vertex_count, version=1, require_complete=False):
    index_count = struct.unpack_from("<I", data)[0]
    width = 4 if vertex_count >= 65535 else 2
    table_start = 4 + index_count * width
    channels = 14 if version >= 1 else 13
    table_bytes = channels * 16
    if table_start + table_bytes > len(data):
        raise ValueError("Truncated descriptor table")
    indices = struct.unpack_from("<" + ("I" if width == 4 else "H") * index_count, data, 4)
    if index_count % 3 or any(i >= vertex_count for i in indices):
        raise ValueError("Invalid triangle indices")
    cursor = table_bytes
    for channel in range(channels):
        offset, size = struct.unpack_from("<QQ", data, table_start + channel * 16)
        if offset != cursor:
            raise ValueError(f"Stream {channel}: offset {offset}, expected {cursor}")
        if table_start + offset + size > len(data):
            raise ValueError(f"Stream {channel} exceeds buffer")
        if size not in (0, vertex_count * STRIDES[channel]):
            raise ValueError(f"Stream {channel}: invalid element count")
        if require_complete and size != vertex_count * STRIDES[channel]:
            raise ValueError(f"Stream {channel}: missing render data")
        cursor += size
    if table_start + cursor != len(data):
        raise ValueError("Unaccounted vertex stream bytes")
    return {
        "vertices": vertex_count,
        "triangles": index_count // 3,
        "channels": channels,
        "bytes": len(data),
    }

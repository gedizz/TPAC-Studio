"""Texture import/preview using layouts documented by MIT-licensed TpacTool.

Only direct pixels are decoded; external streamed texture tiles remain unsupported.
See docs/format-references.md for the exact upstream revision and attribution.
"""

import io
import re
import uuid
from pathlib import Path

from PIL import Image

from .core import Asset, Reader, Segment, TYPES, ZERO, guid, pack, string
from .errors import StudioError, require

PIXELS = uuid.UUID("70ee4e2c-79e4-4b2d-8d54-d53ecd2a559c")


def safe_name(name: str) -> str:
    """Validate a newly authored asset name without renaming existing assets."""
    require(
        isinstance(name, str) and bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", name)),
        "Use a 1–128 character asset name containing letters, digits and underscores, starting with a letter/underscore",
        "INVALID_ARGUMENT",
    )
    return name


def texture_info(asset: Asset) -> dict:
    """Read basic dimensions/format. Do not infer support for unparsed metadata tails."""
    require(asset.type == "Texture", "Expected a texture asset", "UNSUPPORTED")
    reader = Reader(asset.metadata)
    version = reader.n("I")
    require(version <= 2, "Unknown texture metadata version", "UNSUPPORTED")
    reader.take(16)
    reader.n("I")
    reader.s()
    reader.n("Q?I")
    reader.ss()
    reader.n("IB")
    width, height, depth, mipmaps, arrays = reader.n("IIIBH")
    fmt = reader.s()
    return {
        "width": width,
        "height": height,
        "depth": depth,
        "mipmaps": mipmaps,
        "arrays": arrays,
        "format": fmt,
    }


def texture_image(asset: Asset) -> Image.Image:
    """Decode the first mip of a supported 2D texture to RGBA."""
    info = texture_info(asset)
    width, height, fmt = info["width"], info["height"], info["format"]
    require(
        0 < width <= 8192 and 0 < height <= 8192 and width * height <= 16_777_216,
        "Texture exceeds preview pixel budget",
        "RESOURCE_LIMIT",
    )
    require(
        info["arrays"] <= 1 and info["depth"] <= 1,
        "Array/volume texture preview is unsupported",
        "UNSUPPORTED",
    )
    segment = next((s for s in asset.segments if s.kind == PIXELS), None)
    require(segment is not None, "Texture pixels are external or missing", "UNSUPPORTED")
    data = segment.data()
    if fmt.startswith("R8G8B8A8"):
        return Image.frombytes("RGBA", (width, height), data[: width * height * 4])
    if fmt.startswith("B8G8R8A8"):
        return Image.frombytes("RGBA", (width, height), data[: width * height * 4], "raw", "BGRA")
    if fmt == "R8_UNORM":
        return Image.frombytes("L", (width, height), data[: width * height]).convert("RGBA")
    dxgi = {
        "BC1_UNORM": 71,
        "BC1_UNORM_SRGB": 72,
        "BC2_UNORM": 74,
        "BC3_UNORM": 77,
        "BC3_UNORM_SRGB": 78,
        "BC5_UNORM": 83,
        "BC7_UNORM": 98,
        "BC7_UNORM_SRGB": 99,
    }
    require(fmt in dxgi, "Texture format has no preview decoder", "UNSUPPORTED", format=fmt)
    header = (
        pack("7I", 124, 0x81007, height, width, len(data), 0, 1)
        + bytes(44)
        + pack("II4s5I", 32, 4, b"DX10", 0, 0, 0, 0, 0)
        + pack("5I", 0x1000, 0, 0, 0, 0)
    )
    return Image.open(
        io.BytesIO(b"DDS " + header + pack("5I", dxgi[fmt], 3, 0, 1, 0) + data)
    ).convert("RGBA")


def texture_from_image(image: Image.Image, name: str) -> Asset:
    """Author RGBA mipmaps from an owned image; IDs are deterministic by name."""
    name = safe_name(name)
    require(
        image.width * image.height <= 16_777_216,
        "Image exceeds import pixel budget",
        "RESOURCE_LIMIT",
    )
    image = image.convert("RGBA")
    width, height = image.size
    mips = []
    while True:
        mips.append(image.tobytes())
        if image.size == (1, 1):
            break
        image = image.resize(
            (max(1, image.width // 2), max(1, image.height // 2)), Image.Resampling.BOX
        )
    metadata = pack("I", 2) + ZERO.bytes_le + pack("I", 0) + string("") + pack("Q?I", 0, False, 0)
    metadata += pack("I", 0) + pack("IBIIIBH", 1, 2, width, height, 1, len(mips), 1)
    metadata += string("R8G8B8A8_UNORM") + pack("II", 0, 1) + string("has_alpha")
    metadata += pack("IIIQ", 4, 1701736302, 0, 0)
    segment = Segment(guid(name), PIXELS, raw=b"".join(mips))
    return Asset(name, TYPES["Texture"], guid(name), metadata, segments=(segment,))


def import_texture(path: str, name: str) -> Asset:
    """Import an image without executing scripts or changing the source."""
    try:
        with Image.open(Path(path)) as image:
            return texture_from_image(image, name)
    except Image.DecompressionBombError as error:
        raise StudioError("RESOURCE_LIMIT", "Image decompression budget exceeded") from error

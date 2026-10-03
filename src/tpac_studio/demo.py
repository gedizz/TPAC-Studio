"""Original procedural examples; contains no extracted game asset content."""

from PIL import Image, ImageDraw

from .core import Asset, Segment, TYPES, ZERO, guid, pack, string
from .models import model_assets
from .particles import PARTICLE_DATA
from .textures import texture_from_image


def triangle_document() -> dict:
    """A deliberately simple original triangle in metres for import tutorials."""
    vertices = [
        [-0.7, 0, 0, 0, 0, 1, 1, 0, 0, 1, 0, 0],
        [0.7, 0, 0, 0, 0, 1, 1, 0, 0, 1, 1, 0],
        [0, 1, 0, 0, 0, 1, 1, 0, 0, 1, 0.5, 1],
    ]
    return {"groups": [{"vertices": vertices, "indices": [0, 1, 2], "color": [0.2, 0.7, 0.6, 1]}]}


def _curve(default: float = 1.0) -> bytes:
    return pack("IffI", 0, default, 1, 0)


def _parameter(value: float) -> bytes:
    return pack("2I2f", 0, 0, value, 0) + _curve()


def demo_particle() -> Asset:
    """Construct a synthetic emitter for parser/preview/edit demonstrations.

    This fixture is original data, not an engine-certified particle definition.
    Its purpose is exercising documented layouts without distributing game assets.
    """
    name = "demo_smoke"
    data = string("") + pack("II", 0, 1)
    data += (
        pack("I", 1)
        + guid("demo_emitter").bytes_le
        + ZERO.bytes_le * 3
        + string("procedural smoke")
        + pack("II", 0, 0)
    )
    data += (
        string("") * 2
        + pack("fIff5i", 0, 0, 0, 0, 0, 0, 0, 0, 0)
        + pack("18f", *([0] * 18))
        + pack("8f", *([0] * 8))
    )
    data += _parameter(0) + ZERO.bytes_le + string("") * 2
    data += b"".join(_parameter(x) for x in (0, 0, 0.2, 0, 2.5))
    data += pack("2I2f", 0, 0, 1, 0) + _curve() + _curve(0.35)
    data += b"".join(_parameter(x) for x in (12, 0.05, 0, 0.3, 0, 0.2, 0))
    data += pack("IffIffIff", 0, 0, 0, 0, 0, 0, 0, 0, 0) + string("") * 2
    data += pack("II", 0, 2) + pack("5f", 0, 0.8, 0.85, 0.9, 0) + pack("5f", 1, 0.9, 0.9, 0.9, 0)
    data += pack("I", 3) + pack("6f", 0, 0, 0.15, 0.65, 1, 0)
    vectors = [0.0] * 29
    vectors[18] = 0.05
    data += pack("29f", *vectors) + pack("2iIfI", 1, 1, 1, 1, 0)
    data += pack("8fiiI", *([0] * 8), 0, 0, 200) + string("") * 2 + pack("f", 1)
    return Asset(
        name,
        TYPES["Particle"],
        guid(name),
        b"",
        segments=(Segment(guid(name), PARTICLE_DATA, 1, raw=data),),
    )


def demo_assets() -> list[Asset]:
    """Return an authored checker texture, triangle/material and synthetic emitter."""
    image = Image.new("RGBA", (64, 64), (35, 45, 60, 255))
    draw = ImageDraw.Draw(image)
    for x in range(0, 64, 16):
        for y in range(0, 64, 16):
            if (x + y) // 16 % 2:
                draw.rectangle((x, y, x + 15, y + 15), fill=(60, 200, 165, 255))
    return [
        texture_from_image(image, "demo_checker"),
        *model_assets(triangle_document(), "demo_triangle"),
        demo_particle(),
    ]

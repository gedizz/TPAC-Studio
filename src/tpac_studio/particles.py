"""Bounded particle record parsing and conservative field edits.

Binary traversal derives from TpacTool Particle/ParticleEffectData.cs (MIT).
Semantic lifetime/emission mappings are empirical and documented as such; no
engine bytecode, native library or extracted particle definitions are included.
"""

import math
import struct
import uuid
from dataclasses import replace

from .core import Asset, Reader, Segment
from .errors import require
from .settings import PARTICLE_SETTINGS, validate_fields

PARTICLE_DATA = uuid.UUID("326587ce-bb0c-4c22-8782-97e20cf03c5e")


def _curve(reader: Reader) -> dict:
    offset = reader.position
    version, default, multiplier = reader.n("Iff")
    keys = [reader.n("8f") for _ in range(reader.count(4096))]
    return {
        "offset": offset,
        "version": version,
        "default": default,
        "multiplier": multiplier,
        "keys": keys,
    }


def _parameter(reader: Reader) -> dict:
    offset = reader.position
    flags = reader.n("2I")
    values = reader.n("2f")
    return {"offset": offset, "flags": flags, "range": values, "curve": _curve(reader)}


def parse_particle(data: bytes) -> dict:
    """Decode the supported emitter layout with bounded counts and exact tail checks."""
    reader = Reader(data)
    sound = reader.s()
    unknown = reader.n("f" * reader.count(4096))
    emitters = []
    for _ in range(reader.count(1024)):
        version = reader.n("I")
        require(version <= 2, "Unknown particle emitter version", "UNSUPPORTED", version=version)
        guids = [str(reader.guid()) for _ in range(4)]
        emitter = {"version": version, "guids": guids, "name": reader.s()}
        reader.n("I")
        emitter["flags"] = reader.ss()
        reader.s()
        reader.s()
        emitter["pre"] = reader.n("fIff5i")
        emitter["floats"] = reader.n("18f")
        reader.n("8f")
        _parameter(reader)
        reader.guid()
        reader.s()
        reader.s()
        if version >= 2:
            reader.s()
        emitter["p1"] = [_parameter(reader) for _ in range(5)]
        reader.n("2I2f")
        emitter["curves"] = [_curve(reader), _curve(reader)]
        emitter["p2"] = [_parameter(reader) for _ in range(7 if version >= 1 else 6)]
        reader.n("IffIffIff")
        reader.s()
        reader.s()
        reader.n("I")
        emitter["colors"] = [reader.n("5f") for _ in range(reader.count(4096))]
        count = reader.count(4096)
        emitter["alpha_offset"] = reader.position
        emitter["alphas"] = [reader.n("2f") for _ in range(count)]
        emitter["vectors"] = reader.n("4f4f20ff")
        emitter["sprite_offset"] = reader.position
        emitter["sprite"] = reader.n("2i")
        emitter["sprite_animation"] = reader.n("If")
        reader.take(reader.count(4096) * 16)
        reader.n("8fiiI")
        reader.s()
        reader.s()
        reader.n("f")
        emitters.append(emitter)
    require(reader.position == len(data), "Unrecognized particle tail", "UNSUPPORTED")
    return {"sound": sound, "unknown_floats": unknown, "emitters": emitters}


def particle_data(asset: Asset) -> dict:
    """Decode a supported particle payload, without mutation."""
    segment = next((s for s in asset.segments if s.kind == PARTICLE_DATA), None)
    require(segment is not None, "Particle data missing", "UNSUPPORTED")
    require(segment.version == 1, "Unknown particle runtime segment version", "UNSUPPORTED")
    return parse_particle(segment.data())


def edit_particle(asset: Asset, values: dict, *, emitter: int | None = None) -> Asset:
    """Multiply supported fields relative to their current values; preserve other bytes.

    None edits every emitter. Use workspace undo to reverse an edit. Caller commits
    the returned immutable asset only after this whole operation succeeds.
    """
    validate_fields(values, PARTICLE_SETTINGS)
    require(asset.type == "Particle", "Expected particle asset", "UNSUPPORTED")
    require(
        emitter is None or type(emitter) is int and emitter >= 0,
        "Invalid emitter index",
        "INVALID_ARGUMENT",
    )
    segments = []
    changed = False
    for segment in asset.segments:
        if segment.kind != PARTICLE_DATA:
            segments.append(segment)
            continue
        require(segment.version == 1, "Unsupported particle segment version", "UNSUPPORTED")
        raw = bytearray(segment.data())
        records = parse_particle(raw)["emitters"]
        require(emitter is None or emitter < len(records), "Emitter not found", "NOT_FOUND")
        for index, record in enumerate(records):
            if emitter is not None and index != emitter:
                continue
            for key, factor in values.items():
                if key == "opacity":
                    for i, (_, alpha) in enumerate(record["alphas"]):
                        require(math.isfinite(alpha), "Invalid particle alpha")
                        struct.pack_into(
                            "<f",
                            raw,
                            record["alpha_offset"] + i * 8 + 4,
                            max(0, min(1, alpha * factor)),
                        )
                elif key == "size":
                    curve = record["curves"][1]
                    require(math.isfinite(curve["multiplier"]), "Invalid size multiplier")
                    struct.pack_into("<f", raw, curve["offset"] + 8, curve["multiplier"] * factor)
                else:
                    parameter = record["p1"][4] if key == "lifetime" else record["p2"][0]
                    require(
                        all(math.isfinite(x) for x in parameter["range"]), "Invalid emitter range"
                    )
                    struct.pack_into(
                        "<2f",
                        raw,
                        parameter["offset"] + 8,
                        *(x * factor for x in parameter["range"]),
                    )
                    if key == "lifetime":
                        rate = record["sprite_animation"][1]
                        require(math.isfinite(rate), "Invalid sprite rate")
                        struct.pack_into("<f", raw, record["sprite_offset"] + 12, rate / factor)
        parse_particle(raw)
        segments.append(
            Segment(segment.owner, segment.kind, segment.version, segment.flags, raw=bytes(raw))
        )
        changed = True
    require(changed, "No supported particle segment", "UNSUPPORTED")
    return replace(asset, segments=tuple(segments))

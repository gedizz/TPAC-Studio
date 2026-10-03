"""Settings schemas shared by every frontend; units and persistence are explicit."""

import math
from .errors import require

SETTINGS = {
    "preview.fov": {
        "type": "number",
        "minimum": 15,
        "maximum": 100,
        "default": 42,
        "unit": "degrees",
        "scope": "workspace_preview",
    },
    "preview.loop": {"type": "boolean", "default": True, "scope": "workspace_preview"},
    "preview.emitter_speed": {
        "type": "number",
        "minimum": 0,
        "maximum": 80,
        "default": 0,
        "unit": "m/s",
        "scope": "workspace_preview",
    },
}
PARTICLE_SETTINGS = {
    key: {
        "type": "number",
        "minimum": 0.05,
        "maximum": 5,
        "default": 1,
        "unit": "multiplier",
        "scope": "asset",
    }
    for key in ("opacity", "size", "emission", "lifetime")
}


def validate_fields(values: dict, fields: dict) -> dict:
    """Reject unknown keys, bool-as-number, NaN/inf and out-of-range values."""
    require(isinstance(values, dict), "Settings must be an object", "INVALID_ARGUMENT")
    for key, value in values.items():
        require(key in fields, "Unknown setting", "INVALID_ARGUMENT", field=key)
        spec = fields[key]
        if spec["type"] == "boolean":
            require(type(value) is bool, "Setting must be a boolean", "INVALID_ARGUMENT", field=key)
        else:
            require(
                type(value) in (int, float) and math.isfinite(value),
                "Setting must be finite numeric data",
                "INVALID_ARGUMENT",
                field=key,
            )
            require(
                spec["minimum"] <= value <= spec["maximum"],
                "Setting is outside supported range",
                "INVALID_ARGUMENT",
                field=key,
            )
    return dict(values)


def validate_settings(values: dict) -> dict:
    """Merge validated workspace settings over their documented defaults."""
    return {key: value["default"] for key, value in SETTINGS.items()} | validate_fields(
        values, SETTINGS
    )


def settings_schema(fields: dict) -> dict:
    """Return an executable JSON Schema with additional annotation fields."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": fields,
        "additionalProperties": False,
    }

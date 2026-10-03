"""MIT example provider: reuse an existing codec through the extension contract."""

from tpac_studio.core import Asset
from tpac_studio.particles import edit_particle, particle_data


class ExampleOpacity:
    """A narrowly scoped, explicit particle provider; no filesystem side effects."""

    name = "example-opacity"
    api_version = 1
    license = "MIT"

    def supports(self, asset: Asset) -> bool:
        return asset.type == "Particle"

    def inspect(self, asset: Asset) -> dict:
        return {"emitters": len(particle_data(asset)["emitters"])}

    def settings_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"opacity": {"type": "number", "minimum": 0.05, "maximum": 5}},
            "required": ["opacity"],
            "additionalProperties": False,
        }

    def edit(self, asset: Asset, values: dict) -> Asset:
        return edit_particle(asset, values)

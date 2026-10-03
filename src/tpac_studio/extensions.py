"""Explicit, versioned extension registration. Installed plugins are trusted code."""

from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Protocol

from .core import Asset
from .errors import require

EXTENSION_API = 1


class AssetExtension(Protocol):
    """Optional inspector/editor contract; no provider may mutate the workspace directly."""

    name: str
    api_version: int
    license: str

    def supports(self, asset: Asset) -> bool:
        """Return whether this provider understands the record."""
        ...

    def inspect(self, asset: Asset) -> dict:
        """Return bounded JSON metadata; preserve unknown data."""
        ...

    def settings_schema(self) -> dict:
        """Return JSON Schema for supported changes."""
        ...

    def edit(self, asset: Asset, values: dict) -> Asset:
        """Return a replacement immutable asset preserving identity and name."""
        ...


@dataclass
class Registry:
    """Opt-in registry; package/workspace contents cannot trigger plugin loading."""

    providers: dict[str, AssetExtension]

    def __init__(self) -> None:
        self.providers = {}

    def available(self) -> list[dict]:
        """List installed entry-point metadata without executing plugin code."""
        return [
            {"name": entry.name, "target": entry.value}
            for entry in entry_points(group="tpac_studio.extensions")
        ]

    def register(self, provider: AssetExtension) -> None:
        """Register a caller-created provider after contract/version validation."""
        require(provider.api_version == EXTENSION_API, "Unsupported extension API", "UNSUPPORTED")
        require(provider.name not in self.providers, "Extension already loaded", "CONFLICT")
        require(bool(provider.license), "Extension must declare a license", "INVALID_ARGUMENT")
        self.providers[provider.name] = provider

    def load(self, name: str) -> None:
        """Execute an explicitly requested installed entry point. This is not sandboxed."""
        matches = [
            entry for entry in entry_points(group="tpac_studio.extensions") if entry.name == name
        ]
        require(len(matches) == 1, "Extension not found or ambiguous", "NOT_FOUND")
        self.register(matches[0].load()())

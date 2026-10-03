"""Shared typed operations, independent of UI, transport and operating system."""

from __future__ import annotations

import inspect
import math
import threading
import uuid
from pathlib import Path
from typing import Any

from . import __version__
from .core import read_package, write_package
from .errors import StudioError, require
from .extensions import Registry
from .particles import edit_particle, particle_data
from .settings import PARTICLE_SETTINGS, SETTINGS, settings_schema, validate_fields
from .textures import import_texture, texture_image, texture_info
from .workspace import Workspace

API_VERSION = "1"


class Studio:
    """A serialized application session with one workspace and optional extensions.

    GUI, JSON CLI and MCP all call these operations. execute() returns a JSON error
    envelope; direct methods raise StudioError. No background server is implicit.
    """

    def __init__(
        self,
        workspace: Workspace | None = None,
        *,
        root: str | None = None,
        blender: str | None = None,
    ) -> None:
        self.workspace = workspace or Workspace()
        self.root = Path(root).resolve() if root else None
        self.registry = Registry()
        self.blender = blender
        self._lock = threading.RLock()

    def close(self) -> None:
        self.workspace.close()

    def path(self, value: str) -> Path:
        """Resolve a caller path; an optional service root confines agent file access."""
        require(isinstance(value, str) and bool(value), "Path is required", "INVALID_ARGUMENT")
        path = Path(value)
        path = ((self.root / path) if self.root and not path.is_absolute() else path).resolve()
        require(
            self.root is None or path.is_relative_to(self.root),
            "Path is outside the configured service root",
            "PATH_OUTSIDE_ROOT",
            path=str(path),
        )
        return path

    def capabilities(self) -> dict:
        """Discover actual supported operations and feature limitations."""
        return {
            "api_version": API_VERSION,
            "version": __version__,
            "operations": sorted(OPERATIONS),
            "container_versions_read": [1, 2],
            "container_version_write": 2,
            "opaque_repackaging": True,
            "texture_import": True,
            "particle_settings": list(PARTICLE_SETTINGS),
            "animation_decode_authoring": False,
            "dependency_analysis_complete": False,
            "engine_verified": False,
            "gui_live_attachment": False,
            "settings_scopes": ["asset", "workspace_preview"],
            "root": str(self.root) if self.root else None,
        }

    def schemas(self) -> dict:
        """Discover supported settings; unknown keys are always rejected."""
        return {
            "api_version": API_VERSION,
            "workspace": settings_schema(SETTINGS),
            "particle": settings_schema(PARTICLE_SETTINGS),
            "operations": operation_schemas(),
        }

    def workspace_info(self) -> dict:
        """Read current workspace identity/revision and asset counts."""
        return self.workspace.summary()

    def examples_load(self, expected_revision: int | None = None) -> dict:
        """Add original procedural examples; no game files or downloads are used."""
        from .demo import demo_assets

        return self.workspace.add_assets(
            demo_assets(), origin="procedural examples (MIT)", expected_revision=expected_revision
        )

    def workspace_new(self) -> dict:
        """Replace this service workspace. Caller must save wanted edits first."""
        self.workspace.close()
        self.workspace = Workspace()
        return self.workspace.summary()

    def workspace_open(self, path: str) -> dict:
        """Replace the session with a self-contained saved workspace."""
        replacement = Workspace.open(self.path(path))
        self.workspace.close()
        self.workspace = replacement
        return self.workspace.summary()

    def workspace_save(self, path: str, overwrite: bool = False) -> dict:
        """Save the current workspace; detect changes made by another process."""
        return self.workspace.save(self.path(path), overwrite=overwrite)

    def package_inspect(self, path: str) -> dict:
        """Inspect a package table without modifying the current workspace."""
        package = read_package(self.path(path))
        return {
            "package_id": str(package.id),
            "version": package.version,
            "assets": len(package.assets),
            "bytes": package.source.size,
            "sha256": package.source.digest,
            "types": {
                kind: sum(a.type == kind for a in package.assets)
                for kind in sorted({a.type for a in package.assets})
            },
        }

    def package_add(
        self, paths: list[str], conflict: str = "error", expected_revision: int | None = None
    ) -> dict:
        """Atomically add packages. A conflict never prompts in headless interfaces."""
        return self.workspace.add_packages(
            [str(self.path(path)) for path in paths],
            conflict=conflict,
            expected_revision=expected_revision,
        )

    def asset_list(
        self, query: str = "", kind: str = "", source: str = "", offset: int = 0, limit: int = 100
    ) -> dict:
        """List/filter workspace assets with bounded pagination."""
        return self.workspace.list_assets(
            query=query, kind=kind, source=source, offset=offset, limit=limit
        )

    def asset_inspect(self, asset: str) -> dict:
        """Inspect metadata and supported decoded fields; report decoder errors separately."""
        result = self.workspace.inspect(asset)
        record = self.workspace.get(asset)
        try:
            if record.type == "Texture":
                result["decoded"] = texture_info(record)
            elif record.type == "Particle":
                data = particle_data(record)
                result["decoded"] = {
                    "emitters": [
                        {
                            "index": i,
                            "name": e["name"],
                            "version": e["version"],
                            "alpha_keys": e["alphas"],
                            "size_multiplier": e["curves"][1]["multiplier"],
                            "lifetime_range": e["p1"][4]["range"],
                            "emission_range": e["p2"][0]["range"],
                        }
                        for i, e in enumerate(data["emitters"])
                    ]
                }
        except StudioError as error:
            result["decode_error"] = error.as_dict()
        return result

    def asset_select(
        self, assets: list[str], selected: bool, expected_revision: int | None = None
    ) -> dict:
        """Include/exclude exact assets in future plans."""
        return self.workspace.select(assets, selected, expected_revision=expected_revision)

    def asset_remove(self, assets: list[str], expected_revision: int | None = None) -> dict:
        """Remove workspace records only. Original package files remain untouched."""
        return self.workspace.remove(assets, expected_revision=expected_revision)

    def workspace_undo(self, expected_revision: int | None = None) -> dict:
        """Undo one session edit; does not reverse an already-written output file."""
        return self.workspace.undo(expected_revision=expected_revision)

    def dependencies(self) -> dict:
        """Report known references and incomplete-analysis limitations."""
        return self.workspace.dependencies()

    def settings_get(self) -> dict:
        """Return preview settings saved with the workspace."""
        return {"revision": self.workspace.revision, "values": dict(self.workspace.settings)}

    def settings_update(self, values: dict, expected_revision: int | None = None) -> dict:
        """Change schema-validated workspace preview settings."""
        validate_fields(values, SETTINGS)
        self.workspace._before_edit(expected_revision)
        self.workspace.settings.update(values)
        return self.settings_get()

    def particle_edit(
        self,
        asset: str,
        values: dict,
        emitter: int | None = None,
        expected_revision: int | None = None,
    ) -> dict:
        """Scale supported particle fields, optionally for a single emitter index."""
        self.workspace.check_revision(expected_revision)
        edited = edit_particle(self.workspace.get(asset), values, emitter=emitter)
        return self.workspace.replace(edited, expected_revision=expected_revision)

    def texture_import(
        self, path: str, name: str, conflict: str = "error", expected_revision: int | None = None
    ) -> dict:
        """Create RGBA texture mipmaps from a supplied image."""
        self.workspace.check_revision(expected_revision)
        record = import_texture(str(self.path(path)), name)
        return self.workspace.add_assets(
            [record],
            origin="authored image",
            conflict=conflict,
            expected_revision=expected_revision,
        )

    def asset_export(
        self, asset: str, output: str, format: str = "tpac", overwrite: bool = False
    ) -> dict:
        """Export a single record as TPAC or a supported texture as PNG."""
        record = self.workspace.get(asset)
        target = self.path(output)
        if format == "tpac":
            return write_package(
                target, [record], protected=self.workspace.protected, overwrite=overwrite
            ) | {"warning": "Single asset export does not include dependencies"}
        require(format == "png", "Supported exports: tpac, png", "UNSUPPORTED")
        from .core import same_path, sha256_file
        from .workspace import file_lock
        import tempfile
        import os

        require(
            not any(same_path(target, path) for path in self.workspace.protected),
            "Cannot overwrite original source",
            "PROTECTED_SOURCE",
        )
        require(overwrite or not target.exists(), "Output exists", "OUTPUT_EXISTS")
        image = texture_image(record)
        target.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(target):
            fd, temp = tempfile.mkstemp(dir=target.parent, suffix=".building")
            os.close(fd)
            try:
                image.save(temp, format="PNG")
                if overwrite:
                    os.replace(temp, target)
                else:
                    os.link(temp, target)
            finally:
                Path(temp).unlink(missing_ok=True)
        return {"path": str(target), "sha256": sha256_file(target)}

    def model_import(
        self,
        path: str,
        name: str,
        scale: float = 1.0,
        conflict: str = "error",
        expected_revision: int | None = None,
    ) -> dict:
        """Import static geometry JSON, or use host-configured Blender for OBJ/FBX/glTF/BLEND."""
        from .models import import_model

        self.workspace.check_revision(expected_revision)
        assets = import_model(self.path(path), name, scale, self.blender)
        return self.workspace.add_assets(
            assets,
            origin="authored static model",
            conflict=conflict,
            expected_revision=expected_revision,
        )

    def build_plan(self, include_dependencies: bool = True) -> dict:
        """Review the exact asset set and get the required build plan ID."""
        return self.workspace.plan(include_dependencies=include_dependencies)

    def build_execute(
        self,
        output: str,
        plan_id: str,
        include_dependencies: bool = True,
        allow_missing: bool = False,
        overwrite: bool = False,
    ) -> dict:
        """Build the matching current plan, verifying stored output payloads."""
        return self.workspace.build(
            str(self.path(output)),
            plan_id,
            include_dependencies=include_dependencies,
            allow_missing=allow_missing,
            overwrite=overwrite,
        )

    def package_verify(self, path: str) -> dict:
        """Check container bounds and hash every asset; this is not an engine test."""
        package = read_package(self.path(path))
        return {
            "path": str(package.source.path),
            "sha256": package.source.digest,
            "assets": [{"id": str(a.id), "fingerprint": a.fingerprint()} for a in package.assets],
            "structurally_verified": True,
            "engine_verified": False,
        }

    def extensions_list(self) -> dict:
        """Inspect installed/loaded provider metadata without enabling new code."""
        return {
            "available": self.registry.available(),
            "loaded": [
                {"name": p.name, "api_version": p.api_version, "license": p.license}
                for p in self.registry.providers.values()
            ],
        }

    def extension_inspect(self, provider: str, asset: str) -> dict:
        """Inspect an asset through a provider explicitly loaded by the host."""
        require(provider in self.registry.providers, "Provider not enabled by host", "NOT_FOUND")
        extension = self.registry.providers[provider]
        record = self.workspace.get(asset)
        require(extension.supports(record), "Provider does not support asset", "UNSUPPORTED")
        return extension.inspect(record)

    def extension_schema(self, provider: str) -> dict:
        """Discover edit settings from a provider explicitly enabled by the host."""
        require(provider in self.registry.providers, "Provider not enabled by host", "NOT_FOUND")
        return self.registry.providers[provider].settings_schema()

    def extension_edit(
        self, provider: str, asset: str, values: dict, expected_revision: int | None = None
    ) -> dict:
        """Validate a provider edit and commit it with normal identity/revision guards."""
        import jsonschema
        from .core import Asset

        self.workspace.check_revision(expected_revision)
        require(provider in self.registry.providers, "Provider not enabled by host", "NOT_FOUND")
        extension = self.registry.providers[provider]
        record = self.workspace.get(asset)
        require(extension.supports(record), "Provider does not support asset", "UNSUPPORTED")
        jsonschema.validate(values, extension.settings_schema())
        _finite(values)
        edited = extension.edit(record, values)
        require(isinstance(edited, Asset), "Provider must return an Asset", "INVALID_ARGUMENT")
        require(edited.kind == record.kind, "Provider cannot change asset type", "INVALID_ARGUMENT")
        return self.workspace.replace(edited, expected_revision=expected_revision)

    def execute(
        self, operation: str, arguments: dict | None = None, *, request_id: str | None = None
    ) -> dict:
        """Validate and execute one JSON request, returning a stable result envelope."""
        request_id = request_id or str(uuid.uuid4())
        with self._lock:
            try:
                require(
                    operation in OPERATIONS, "Unknown operation", "NOT_FOUND", operation=operation
                )
                arguments = arguments if arguments is not None else {}
                require(
                    isinstance(arguments, dict), "Arguments must be an object", "INVALID_ARGUMENT"
                )
                import jsonschema

                jsonschema.validate(arguments, operation_schemas()[operation])
                _finite(arguments)
                result = getattr(self, operation)(**arguments)
                import json

                json.dumps(result, allow_nan=False)
                return {
                    "api_version": API_VERSION,
                    "request_id": request_id,
                    "ok": True,
                    "revision": self.workspace.revision,
                    "result": result,
                    "warnings": [],
                }
            except StudioError as error:
                return {
                    "api_version": API_VERSION,
                    "request_id": request_id,
                    "ok": False,
                    "revision": self.workspace.revision,
                    "error": error.as_dict(),
                }
            except (OSError, ValueError, KeyError, TypeError, OverflowError) as error:
                return {
                    "api_version": API_VERSION,
                    "request_id": request_id,
                    "ok": False,
                    "revision": self.workspace.revision,
                    "error": {
                        "code": "INVALID_ARGUMENT"
                        if not isinstance(error, OSError)
                        else "IO_ERROR",
                        "message": str(error),
                        "details": {},
                    },
                }
            except Exception as error:
                # ValidationError is intentionally normalized; other failures are not
                # disguised as successes. Local debug traces belong in stderr logs.
                import jsonschema

                code = (
                    "INVALID_ARGUMENT"
                    if isinstance(error, jsonschema.ValidationError)
                    else "INTERNAL_ERROR"
                )
                return {
                    "api_version": API_VERSION,
                    "request_id": request_id,
                    "ok": False,
                    "revision": self.workspace.revision,
                    "error": {"code": code, "message": str(error), "details": {}},
                }


def _finite(value: Any) -> None:
    if isinstance(value, float):
        require(math.isfinite(value), "JSON numbers must be finite", "INVALID_ARGUMENT")
    elif isinstance(value, dict):
        for item in value.values():
            _finite(item)
    elif isinstance(value, list):
        for item in value:
            _finite(item)


OPERATIONS = {
    name
    for name, method in inspect.getmembers(Studio, inspect.isfunction)
    if name not in {"close", "path", "execute"} and not name.startswith("_")
}


def operation_schemas() -> dict:
    """Derive JSON argument contracts from public signatures and constrain edits."""
    from typing import get_type_hints, get_origin, get_args
    import types

    def schema(annotation):
        if get_origin(annotation) is types.UnionType:
            return {"anyOf": [schema(a) for a in get_args(annotation)]}
        if get_origin(annotation) is list:
            return {"type": "array", "items": schema(get_args(annotation)[0]), "maxItems": 100_000}
        return {
            "type": {
                str: "string",
                int: "integer",
                float: "number",
                bool: "boolean",
                dict: "object",
                type(None): "null",
            }.get(annotation, "object")
        }

    result = {}
    for name in OPERATIONS:
        method = getattr(Studio, name)
        hints = get_type_hints(method)
        properties = {}
        required = []
        for key, parameter in inspect.signature(method).parameters.items():
            if key == "self":
                continue
            properties[key] = schema(hints[key])
            if parameter.default is inspect.Parameter.empty:
                required.append(key)
            else:
                properties[key]["default"] = parameter.default
        if "conflict" in properties:
            properties["conflict"]["enum"] = ["error", "keep", "replace"]
        if name in ("settings_update", "particle_edit"):
            properties["values"] = settings_schema(
                SETTINGS if name == "settings_update" else PARTICLE_SETTINGS
            )
        result[name] = {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
            "description": inspect.getdoc(method),
        }
    return result

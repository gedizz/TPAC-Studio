"""Editable, revisioned workspaces shared by all TPAC Studio frontends."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from .core import Asset, Source, read_package, same_path, sha256_file, write_package
from .errors import StudioError, require


def canonical(value: object) -> bytes:
    """Stable JSON encoding for plan identity, never for shell interpolation."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


@contextmanager
def file_lock(path: Path):
    """Cross-process advisory lock; stale locks are reported, never auto-deleted."""
    lock = path.with_name(path.name + ".lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise StudioError(
            "WORKSPACE_BUSY", "Another process owns the file lock", path=str(lock)
        ) from error
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


class Workspace:
    """In-memory assets with atomic edits, undo, source protection and build plans.

    Use as a context manager to release temporary backing files after open().
    Mutations increment revision. Saved workspaces contain their own payloads.
    Access from multiple threads must be serialized by the caller/service.
    """

    def __init__(self) -> None:
        self.id = str(uuid.uuid4())
        self.revision = 0
        self._assets: dict[uuid.UUID, Asset] = {}
        self.selected: set[uuid.UUID] = set()
        self.known: dict[uuid.UUID, str] = {}
        self.origins: dict[uuid.UUID, str] = {}
        self.protected: set[Path] = set()
        self.settings = {"preview.fov": 42.0, "preview.loop": True, "preview.emitter_speed": 0.0}
        self._history: list[tuple] = []
        self._temporary: list[tempfile.TemporaryDirectory] = []
        self._project: Path | None = None
        self._project_hash: str | None = None

    def __enter__(self) -> Workspace:
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def close(self) -> None:
        """Release self-contained workspace backing files; do not delete source files."""
        for directory in self._temporary:
            directory.cleanup()
        self._temporary.clear()

    @property
    def assets(self) -> tuple[Asset, ...]:
        return tuple(self._assets.values())

    def check_revision(self, expected: int | None) -> None:
        require(
            expected is None or expected == self.revision,
            "Workspace revision changed",
            "STALE_REVISION",
            expected=expected,
            actual=self.revision,
        )

    def _before_edit(self, expected: int | None = None) -> None:
        self.check_revision(expected)
        self._history.append(
            (dict(self._assets), set(self.selected), dict(self.origins), dict(self.settings))
        )
        self._history = self._history[-30:]
        self.revision += 1

    def undo(self, *, expected_revision: int | None = None) -> dict:
        """Undo the last edit; revisions remain monotonic. History is session-local."""
        self.check_revision(expected_revision)
        require(bool(self._history), "No edit to undo", "NOT_FOUND")
        self._assets, self.selected, self.origins, self.settings = self._history.pop()
        self.revision += 1
        return self.summary()

    def summary(self) -> dict:
        return {
            "workspace_id": self.id,
            "revision": self.revision,
            "assets": len(self._assets),
            "selected": len(self.selected),
            "undo_available": bool(self._history),
        }

    def get(self, identity: str | uuid.UUID) -> Asset:
        """Resolve a GUID or an unambiguous exact name."""
        try:
            key = uuid.UUID(str(identity))
            if key in self._assets:
                return self._assets[key]
        except ValueError:
            pass
        matches = [asset for asset in self.assets if asset.name == str(identity)]
        require(len(matches) == 1, "Asset not found or ambiguous", "NOT_FOUND", asset=str(identity))
        return matches[0]

    def list_assets(
        self,
        *,
        query: str = "",
        kind: str = "",
        source: str = "",
        offset: int = 0,
        limit: int = 100,
    ) -> dict:
        """Filter and paginate assets; pagination is tied to the returned revision."""
        require(
            isinstance(offset, int)
            and offset >= 0
            and isinstance(limit, int)
            and 1 <= limit <= 1000,
            "Invalid pagination",
            "INVALID_ARGUMENT",
        )
        matches = [
            asset
            for asset in self.assets
            if query.casefold() in asset.name.casefold()
            and (not kind or asset.type == kind)
            and (not source or source in self.origins.get(asset.id, ""))
        ]
        matches.sort(key=lambda asset: (asset.type, asset.name, str(asset.id)))
        page = [
            asset.summary()
            | {
                "selected": asset.id in self.selected,
                "source": self.origins.get(asset.id, "authored"),
            }
            for asset in matches[offset : offset + limit]
        ]
        return {
            "revision": self.revision,
            "total": len(matches),
            "items": page,
            "next_offset": offset + limit if offset + limit < len(matches) else None,
        }

    def inspect(self, identity: str) -> dict:
        """Describe a record without requiring a payload decoder."""
        asset = self.get(identity)
        return asset.summary() | {
            "source": self.origins.get(asset.id),
            "metadata_bytes": len(asset.metadata),
            "dependency_records": len(asset.dependencies) // 48,
            "fingerprint": asset.fingerprint(),
            "segments_detail": [
                {
                    "owner": str(s.owner),
                    "type_id": str(s.kind),
                    "version": s.version,
                    "flags": s.flags,
                    "storage": s.storage,
                    "stored_bytes": s.size,
                    "decoded_bytes": s.decoded_size,
                }
                for s in asset.segments
            ],
        }

    def add_assets(
        self,
        assets: Iterable[Asset],
        *,
        origin: str = "authored",
        conflict: str = "error",
        expected_revision: int | None = None,
    ) -> dict:
        """Atomically merge records. Policies: error, keep, replace (same GUID only)."""
        self.check_revision(expected_revision)
        require(
            conflict in ("error", "keep", "replace"), "Unknown conflict policy", "INVALID_ARGUMENT"
        )
        incoming = tuple(assets)
        result = dict(self._assets)
        origins = dict(self.origins)
        decisions = []
        for asset in incoming:
            old = result.get(asset.id)
            name_conflict = next(
                (a for a in result.values() if a.name == asset.name and a.id != asset.id), None
            )
            if name_conflict:
                require(
                    conflict == "keep",
                    "Name belongs to another GUID; no implicit ID rewrite",
                    "CONFLICT",
                    incoming=asset.summary(),
                    existing=name_conflict.summary(),
                )
                decisions.append({"id": str(asset.id), "action": "kept_existing_name"})
                continue
            if old:
                if old.fingerprint() == asset.fingerprint():
                    decisions.append({"id": str(asset.id), "action": "identical"})
                    continue
                require(
                    conflict != "error",
                    "GUID has different contents",
                    "CONFLICT",
                    incoming=asset.summary(),
                    existing=old.summary(),
                )
                if conflict == "keep":
                    decisions.append({"id": str(asset.id), "action": "kept_existing"})
                    continue
            result[asset.id] = asset
            origins[asset.id] = origin
            decisions.append({"id": str(asset.id), "action": "replaced" if old else "added"})
        self._before_edit(expected_revision)
        new_ids = set(result) - set(self._assets)
        self._assets, self.origins = result, origins
        self.selected.update(new_ids)
        self.known.update({asset.id: asset.name for asset in incoming})
        return self.summary() | {"decisions": decisions}

    def add_packages(
        self, paths: list[str], *, conflict: str = "error", expected_revision: int | None = None
    ) -> dict:
        """Read every input before changing state. Any conflict cancels the batch."""
        self.check_revision(expected_revision)
        packages = [read_package(path) for path in paths]
        staged = Workspace()
        staged._assets = dict(self._assets)
        staged.origins = dict(self.origins)
        staged.selected = set(self.selected)
        staged.known = dict(self.known)
        decisions = []
        for package in packages:
            decisions += staged.add_assets(
                package.assets, origin=str(package.source.path), conflict=conflict
            )["decisions"]
        self._before_edit(expected_revision)
        self._assets, self.origins, self.selected, self.known = (
            staged._assets,
            staged.origins,
            staged.selected,
            staged.known,
        )
        self.protected.update(package.source.path for package in packages)
        return self.summary() | {"decisions": decisions}

    def select(
        self, identities: list[str], selected: bool, *, expected_revision: int | None = None
    ) -> dict:
        """Change build inclusion for exact IDs/names; an empty list changes nothing."""
        require(isinstance(selected, bool), "selected must be a boolean", "INVALID_ARGUMENT")
        ids = {self.get(identity).id for identity in identities}
        self._before_edit(expected_revision)
        self.selected = self.selected | ids if selected else self.selected - ids
        return self.summary()

    def remove(self, identities: list[str], *, expected_revision: int | None = None) -> dict:
        """Remove records from workspace only; remember IDs to detect dangling links."""
        ids = {self.get(identity).id for identity in identities}
        self._before_edit(expected_revision)
        self._assets = {key: value for key, value in self._assets.items() if key not in ids}
        self.selected -= ids
        return self.summary() | {"removed": sorted(str(key) for key in ids)}

    def replace(self, asset: Asset, *, expected_revision: int | None = None) -> dict:
        """Commit a validated codec edit while keeping identity/source ownership."""
        require(
            asset.id in self._assets and asset.name == self._assets[asset.id].name,
            "An edit must preserve asset identity/name",
            "INVALID_ARGUMENT",
        )
        self._before_edit(expected_revision)
        self._assets[asset.id] = asset
        return self.summary()

    def sources(self) -> set[Source]:
        return {
            segment.source for asset in self.assets for segment in asset.segments if segment.source
        } | {asset.source for asset in self.assets if asset.source}

    def dependencies(self) -> dict:
        """Conservative GUID matching, explicitly distinguished from complete resolution."""
        links = {}
        warnings = []
        known_bytes = {identity.bytes_le: str(identity) for identity in self.known}
        remaining = 64 * 1024**2
        for asset in self.assets:
            chunks = [asset.metadata, asset.dependencies]
            if asset.type == "Particle":
                for segment in asset.segments:
                    try:
                        chunks.append(segment.data())
                    except StudioError as error:
                        warnings.append({"asset": str(asset.id), "error": error.as_dict()})
            found = set()
            for chunk in chunks:
                permitted = min(len(chunk), remaining)
                data = chunk[:permitted]
                remaining -= permitted
                if len(known_bytes) <= 128:
                    found.update(identity for raw, identity in known_bytes.items() if raw in data)
                else:
                    # Linear in inspected bytes, rather than assets squared for large libraries.
                    found.update(
                        known_bytes[value]
                        for index in range(max(0, len(data) - 15))
                        if (value := data[index : index + 16]) in known_bytes
                    )
                if permitted < len(chunk):
                    warnings.append(
                        {
                            "asset": str(asset.id),
                            "code": "ANALYSIS_LIMIT",
                            "message": "64 MiB reference scan budget reached; references may be omitted",
                        }
                    )
            found.discard(str(asset.id))
            links[str(asset.id)] = sorted(found)
        return {
            "links": links,
            "warnings": warnings,
            "method": "known_guid_byte_matching",
            "complete": False,
            "limitations": [
                "External asset IDs not previously loaded are not resolved",
                "Opaque payload references and XML links are not certified",
            ],
        }

    def plan(self, *, include_dependencies: bool = True) -> dict:
        """Compute a deterministic build proposal bound to content and revision."""
        require(
            isinstance(include_dependencies, bool),
            "include_dependencies must be boolean",
            "INVALID_ARGUMENT",
        )
        for source in self.sources():
            source.verify()
        analysis = self.dependencies()
        selected = set(self.selected)
        graph = {
            uuid.UUID(key): {uuid.UUID(value) for value in values}
            for key, values in analysis["links"].items()
        }
        if include_dependencies:
            while True:
                extra = {
                    link
                    for identity in selected
                    for link in graph[identity]
                    if link in self._assets
                } - selected
                if not extra:
                    break
                selected.update(extra)
        chosen = sorted((self._assets[key] for key in selected), key=lambda a: str(a.id))
        missing = sorted(
            (str(identity), str(link))
            for identity in selected
            for link in graph[identity]
            if link not in selected
        )
        result = {
            "workspace_id": self.id,
            "revision": self.revision,
            "include_dependencies": include_dependencies,
            "assets": [asset.summary() for asset in chosen],
            "fingerprints": {str(a.id): a.fingerprint() for a in chosen},
            "auto_included": sorted(str(key) for key in selected - self.selected),
            "missing_known_references": [
                {"from": key, "to": value, "target_name": self.known[uuid.UUID(value)]}
                for key, value in missing
            ],
            "bytes": sum(asset.size for asset in chosen),
            "dependency_analysis": analysis,
            "engine_verified": False,
        }
        result["plan_id"] = hashlib.sha256(canonical(result)).hexdigest()
        return result

    def build(
        self,
        output: str,
        plan_id: str,
        *,
        include_dependencies: bool = True,
        allow_missing: bool = False,
        overwrite: bool = False,
    ) -> dict:
        """Execute the exact current plan; never silently execute a stale proposal."""
        plan = self.plan(include_dependencies=include_dependencies)
        require(plan["plan_id"] == plan_id, "Plan no longer matches workspace/inputs", "STALE_PLAN")
        require(
            allow_missing or not plan["missing_known_references"],
            "Plan has excluded/removed references",
            "MISSING_DEPENDENCIES",
            missing=plan["missing_known_references"],
        )
        assets = [self._assets[uuid.UUID(asset["id"])] for asset in plan["assets"]]
        report = write_package(output, assets, protected=self.protected, overwrite=overwrite)
        return report | {
            "plan_id": plan_id,
            "dependency_analysis_complete": False,
            "missing_accepted": plan["missing_known_references"],
        }

    def save(self, path: str | Path, *, overwrite: bool = False) -> dict:
        """Save a self-contained ZIP workspace with optimistic and advisory locking."""
        target = Path(path).resolve()
        require(
            not any(same_path(target, source) for source in self.protected),
            "Cannot replace an original package",
            "PROTECTED_SOURCE",
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(target):
            if self._project == target:
                require(
                    target.exists() and sha256_file(target) == self._project_hash,
                    "Saved workspace changed in another process",
                    "STALE_WORKSPACE",
                )
            else:
                require(
                    overwrite or not target.exists(), "Workspace already exists", "OUTPUT_EXISTS"
                )
            with tempfile.TemporaryDirectory(prefix="tpac-save-") as folder:
                package = Path(folder) / "contents.tpac"
                if self.assets:
                    write_package(package, self.assets, protected=self.protected)
                config = {
                    "version": 1,
                    "id": self.id,
                    "revision": self.revision,
                    "selected": sorted(str(key) for key in self.selected),
                    "known": {str(key): name for key, name in self.known.items()},
                    "origins": {str(key): value for key, value in self.origins.items()},
                    "protected": sorted(str(path) for path in self.protected),
                    "settings": self.settings,
                }
                fd, temporary = tempfile.mkstemp(dir=target.parent, suffix=".building")
                os.close(fd)
                try:
                    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_STORED) as archive:
                        archive.writestr("workspace.json", canonical(config))
                        if self.assets:
                            archive.write(package, "contents.tpac")
                    os.replace(temporary, target)
                finally:
                    Path(temporary).unlink(missing_ok=True)
        self._project, self._project_hash = target, sha256_file(target)
        return self.summary() | {"path": str(target), "sha256": self._project_hash}

    @classmethod
    def open(cls, path: str | Path) -> Workspace:
        """Load only expected ZIP members; never extract arbitrary archive paths."""
        target = Path(path).resolve(strict=True)
        digest = sha256_file(target)
        result = cls()
        directory = tempfile.TemporaryDirectory(prefix="tpac-project-")
        result._temporary.append(directory)
        try:
            with zipfile.ZipFile(target) as archive:
                names = archive.namelist()
                require(
                    len(names) == len(set(names))
                    and set(names) <= {"workspace.json", "contents.tpac"},
                    "Unexpected or duplicate workspace entries",
                    "INVALID_DATA",
                )
                config_info = archive.getinfo("workspace.json")
                require(
                    config_info.file_size <= 16 * 1024**2,
                    "Workspace metadata too large",
                    "RESOURCE_LIMIT",
                )
                config = json.loads(archive.read(config_info))
                require(config.get("version") == 1, "Unsupported workspace version", "UNSUPPORTED")
                if "contents.tpac" in archive.namelist():
                    info = archive.getinfo("contents.tpac")
                    require(
                        info.file_size <= 8 * 1024**3,
                        "Workspace exceeds 8 GiB limit",
                        "RESOURCE_LIMIT",
                    )
                    package = Path(directory.name) / "contents.tpac"
                    with archive.open(info) as source, package.open("wb") as destination:
                        shutil.copyfileobj(source, destination, 1024**2)
                    assets = read_package(package).assets
                    result._assets = {asset.id: asset for asset in assets}
                    require(len(result._assets) == len(assets), "Workspace has duplicate IDs")
            result.id = str(uuid.UUID(config["id"]))
            result.revision = config["revision"]
            require(type(result.revision) is int and result.revision >= 0, "Invalid revision")
            result.selected = {uuid.UUID(key) for key in config["selected"]}
            require(
                result.selected <= result._assets.keys(), "Selection includes nonexistent assets"
            )
            result.known = {uuid.UUID(key): name for key, name in config["known"].items()}
            result.known.update({a.id: a.name for a in result.assets})
            result.origins = {uuid.UUID(key): name for key, name in config["origins"].items()}
            result.protected = {Path(value).resolve() for value in config["protected"]}
            from .settings import validate_settings

            result.settings = validate_settings(config["settings"])
            require(
                sha256_file(target) == digest, "Workspace changed while opening", "STALE_WORKSPACE"
            )
            result._project, result._project_hash = target, digest
            return result
        except Exception:
            result.close()
            raise

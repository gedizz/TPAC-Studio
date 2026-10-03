"""Bounded TPAC v1/v2 container I/O; payloads remain opaque unless explicitly decoded.

Layout reference: MIT-licensed TpacTool, Package/AssetPackage.cs at the revision
recorded in docs/provenance.md. See LICENSES/TpacTool-MIT.txt for attribution.
No TaleWorlds library is imported. Reads and writes do not execute asset content.
"""

from __future__ import annotations

import hashlib
import os
import struct
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Iterable

from .errors import StudioError, require

MAGIC = 0x43415054
ZERO = uuid.UUID(int=0)
NAMESPACE = uuid.UUID("f87fb564-c219-4737-9cb4-0dfca583c533")
MAX_TABLE = 128 * 1024**2
MAX_COUNT = 100_000
MAX_DECODE = 256 * 1024**2
CHUNK = 1024**2
KINDS = {
    "a08f8b97-197c-4bea-b95b-53846cae834e": "Mesh",
    "c974cbcb-5f1c-49f6-9a32-2b5b6c92c2e8": "Texture",
    "1db01393-6902-4f19-83ba-b37a39830717": "Material",
    "506509c8-e563-4ca4-b166-a53b92e913a7": "Animation",
    "bafab007-7e3f-453f-bac6-e7640043112b": "Animation source",
    "6de14d67-dd9a-45be-9463-0281c3d8dd51": "Particle",
}
TYPES = {value: uuid.UUID(key) for key, value in KINDS.items()}


def guid(name: str) -> uuid.UUID:
    """Return the deterministic identity for a newly authored asset name."""
    return uuid.uuid5(NAMESPACE, name)


def pack(fmt: str, *values: object) -> bytes:
    """Encode little-endian TPAC fields."""
    return struct.pack("<" + fmt, *values)


def string(value: str) -> bytes:
    """Encode a length-prefixed UTF-8 TPAC string."""
    data = value.encode("utf8")
    return pack("I", len(data)) + data


class Reader:
    """Cursor reader which rejects short reads and unbounded count fields."""

    def __init__(self, data: bytes) -> None:
        self.data = bytes(data)
        self.position = 0

    def take(self, size: int) -> bytes:
        require(0 <= size <= len(self.data) - self.position, "Truncated binary record")
        start = self.position
        self.position += size
        return self.data[start : self.position]

    def n(self, fmt: str):
        values = struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))
        return values[0] if len(values) == 1 else values

    def count(self, maximum: int = MAX_COUNT) -> int:
        value = self.n("I")
        require(value <= maximum, "Count exceeds supported limit", value=value, limit=maximum)
        return value

    def s(self) -> str:
        try:
            return self.take(self.count(1024**2)).decode("utf8")
        except UnicodeError as error:
            raise StudioError("INVALID_DATA", "Asset string is not UTF-8") from error

    def ss(self) -> list[str]:
        return [self.s() for _ in range(self.count())]

    def guid(self) -> uuid.UUID:
        return uuid.UUID(bytes_le=self.take(16))


def sha256_file(path: Path) -> str:
    """Hash a file incrementally, independent of its total size."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@dataclass(frozen=True)
class Source:
    """Immutable source fingerprint, checked before plans and writes."""

    path: Path
    size: int
    digest: str

    @classmethod
    def capture(cls, path: str | Path) -> Source:
        resolved = Path(path).resolve(strict=True)
        return cls(resolved, resolved.stat().st_size, sha256_file(resolved))

    def verify(self) -> None:
        require(
            self.path.is_file()
            and self.path.stat().st_size == self.size
            and sha256_file(self.path) == self.digest,
            "An open source package changed or disappeared; reopen it",
            "SOURCE_CHANGED",
            path=str(self.path),
        )


@dataclass(frozen=True)
class Segment:
    """Stored bytes or a lazy slice of an immutable source; compressed bytes stay intact."""

    owner: uuid.UUID
    kind: uuid.UUID
    version: int = 0
    flags: int = 0
    storage: int = 0
    raw: bytes | None = None
    source: Source | None = None
    offset: int = 0
    stored_size: int = 0
    actual_size: int = 0

    @property
    def size(self) -> int:
        return len(self.raw) if self.raw is not None else self.stored_size

    @property
    def decoded_size(self) -> int:
        return self.actual_size if self.storage else self.size

    def chunks(self) -> Iterable[bytes]:
        """Yield stored bytes without allocating the complete payload."""
        if self.raw is not None:
            for index in range(0, len(self.raw), CHUNK):
                yield self.raw[index : index + CHUNK]
            return
        require(self.source is not None, "Segment has no backing data")
        with self.source.path.open("rb") as stream:
            stream.seek(self.offset)
            remaining = self.stored_size
            while remaining:
                data = stream.read(min(CHUNK, remaining))
                require(bool(data), "Source segment is truncated", "SOURCE_CHANGED")
                remaining -= len(data)
                yield data

    def digest(self) -> str:
        """Hash the exact stored representation, including compression."""
        digest = hashlib.sha256()
        for chunk in self.chunks():
            digest.update(chunk)
        return digest.hexdigest()

    def data(self, limit: int = MAX_DECODE) -> bytes:
        """Decode raw/LZ4 payloads with a memory limit; opaque copying supports any mode."""
        require(
            self.size <= limit and self.decoded_size <= limit,
            "Segment exceeds decode limit",
            "RESOURCE_LIMIT",
        )
        data = b"".join(self.chunks())
        if self.storage == 0:
            return data
        if self.storage != 1:
            raise StudioError(
                "UNSUPPORTED",
                "Unknown compression; opaque repackaging remains available",
                storage=self.storage,
            )
        import lz4.block

        try:
            return lz4.block.decompress(data, uncompressed_size=self.actual_size)
        except lz4.block.LZ4BlockError as error:
            raise StudioError("INVALID_DATA", "Invalid LZ4 payload") from error


@dataclass(frozen=True)
class Asset:
    """One TPAC table record. Asset/segment identities are preserved when repackaging."""

    name: str
    kind: uuid.UUID
    id: uuid.UUID
    metadata: bytes = b""
    version: int = 0
    segments: tuple[Segment, ...] = field(default_factory=tuple)
    dependencies: bytes = b""
    checksum: bytes = bytes(8)
    source: Source | None = None

    @property
    def type(self) -> str:
        return KINDS.get(str(self.kind), "Other")

    @property
    def size(self) -> int:
        return len(self.metadata) + sum(segment.size for segment in self.segments)

    def fingerprint(self) -> str:
        """Content fingerprint independent of source paths and package offsets."""
        digest = hashlib.sha256()
        for value in (
            string(self.name),
            self.kind.bytes_le,
            self.id.bytes_le,
            pack("I", self.version),
            self.metadata,
            self.dependencies,
            self.checksum,
        ):
            digest.update(pack("Q", len(value)))
            digest.update(value)
        for segment in self.segments:
            digest.update(segment.owner.bytes_le + segment.kind.bytes_le)
            digest.update(
                pack(
                    "IQBQQ",
                    segment.version,
                    segment.flags,
                    segment.storage,
                    segment.size,
                    segment.decoded_size,
                )
            )
            digest.update(bytes.fromhex(segment.digest()))
        return digest.hexdigest()

    def summary(self) -> dict:
        """JSON metadata for listings; never emits large binary payloads."""
        return {
            "id": str(self.id),
            "name": self.name,
            "type": self.type,
            "type_id": str(self.kind),
            "version": self.version,
            "bytes": self.size,
            "segments": len(self.segments),
        }


@dataclass(frozen=True)
class Package:
    """Parsed source package with its original package identity."""

    id: uuid.UUID
    version: int
    source: Source
    assets: tuple[Asset, ...]


def read_package(path: str | Path) -> Package:
    """Read a bounded table and retain lazy payload slices; v1/v2 are supported."""
    source = Source.capture(path)
    with source.path.open("rb") as stream:
        header = Reader(stream.read(36))
        magic, version = header.n("II")
        require(
            magic == MAGIC and version in (1, 2),
            "Only TPAC v1/v2 containers are supported",
            "UNSUPPORTED",
        )
        identity = header.guid()
        count, table_size, reserved = header.n("III")
        require(reserved == 0, "Unknown container header flags", "UNSUPPORTED")
        require(
            count <= MAX_COUNT and table_size <= MAX_TABLE and 36 + table_size <= source.size,
            "Invalid TPAC table bounds",
        )
        reader = Reader(stream.read(table_size))
        assets = []
        for _ in range(count):
            kind, aid = reader.guid(), reader.guid()
            asset_version = reader.n("I") if version == 2 else 0
            name = reader.s()
            metadata = reader.take(reader.n("Q"))
            checksum = reader.take(8)
            segments = []
            for _ in range(reader.count()):
                offset, actual, stored = reader.n("QQQ")
                owner, segment_kind = reader.guid(), reader.guid()
                flags, segment_version, storage = reader.n("QIB")
                require(
                    offset >= 36 + table_size and offset + stored <= source.size,
                    "Segment lies outside package",
                )
                segments.append(
                    Segment(
                        owner,
                        segment_kind,
                        segment_version,
                        flags,
                        storage,
                        None,
                        source,
                        offset,
                        stored,
                        actual,
                    )
                )
            dependencies = reader.take(reader.count() * 48)
            assets.append(
                Asset(
                    name,
                    kind,
                    aid,
                    metadata,
                    asset_version,
                    tuple(segments),
                    dependencies,
                    checksum,
                    source,
                )
            )
        require(reader.position == len(reader.data), "Unexpected table tail", "UNSUPPORTED")
    source.verify()
    return Package(identity, version, source, tuple(assets))


def same_path(left: Path, right: Path) -> bool:
    """Compare normalized paths and existing hardlink aliases."""
    if left.resolve() == right.resolve():
        return True
    return left.exists() and right.exists() and os.path.samefile(left, right)


def validate_assets(assets: Iterable[Asset]) -> tuple[Asset, ...]:
    """Check container invariants without imposing a format-specific decoder."""
    assets = tuple(assets)
    require(0 < len(assets) <= MAX_COUNT, "Build requires 1–100000 assets")
    names, identities = set(), set()
    for asset in assets:
        require(
            bool(asset.name) and asset.name not in names,
            "Duplicate/empty asset name",
            "CONFLICT",
            name=asset.name,
        )
        require(
            asset.id not in identities, "Duplicate asset identity", "CONFLICT", id=str(asset.id)
        )
        require(
            len(asset.dependencies) % 48 == 0 and len(asset.checksum) == 8,
            "Invalid dependency/checksum record",
        )
        names.add(asset.name)
        identities.add(asset.id)
    return assets


def _write(stream: BinaryIO, assets: tuple[Asset, ...], identity: uuid.UUID) -> None:
    table_size = sum(
        16
        + 16
        + 4
        + len(string(a.name))
        + 8
        + len(a.metadata)
        + 8
        + 4
        + 69 * len(a.segments)
        + 4
        + len(a.dependencies)
        for a in assets
    )
    require(table_size <= MAX_TABLE, "Output table exceeds size limit", "RESOURCE_LIMIT")
    stream.write(pack("II", MAGIC, 2) + identity.bytes_le + pack("III", len(assets), table_size, 0))
    offset = 36 + table_size
    for asset in assets:
        stream.write(
            asset.kind.bytes_le
            + asset.id.bytes_le
            + pack("I", asset.version)
            + string(asset.name)
            + pack("Q", len(asset.metadata))
            + asset.metadata
            + asset.checksum
            + pack("I", len(asset.segments))
        )
        for segment in asset.segments:
            stream.write(
                pack("QQQ", offset, segment.decoded_size, segment.size)
                + segment.owner.bytes_le
                + segment.kind.bytes_le
                + pack("QIB", segment.flags, segment.version, segment.storage)
            )
            offset += segment.size
        stream.write(pack("I", len(asset.dependencies) // 48) + asset.dependencies)
    for asset in assets:
        for segment in asset.segments:
            for chunk in segment.chunks():
                stream.write(chunk)


def write_package(
    path: str | Path,
    assets: Iterable[Asset],
    *,
    package_id: uuid.UUID | None = None,
    protected: Iterable[Path] = (),
    overwrite: bool = False,
) -> dict:
    """Atomically write a new package after a verified round trip.

    Existing outputs require overwrite=True. Source files (including hardlinks)
    are protected even with overwrite=True. No companion files are implicit.
    """
    target = Path(path).resolve()
    assets = validate_assets(assets)
    sources = {
        segment.source for asset in assets for segment in asset.segments if segment.source
    } | {asset.source for asset in assets if asset.source}
    guards = set(protected) | {source.path for source in sources}
    require(
        not any(same_path(target, Path(p)) for p in guards),
        "Cannot overwrite an original source package",
        "PROTECTED_SOURCE",
    )
    require(
        overwrite or not target.exists(), "Output already exists", "OUTPUT_EXISTS", path=str(target)
    )
    for source in sources:
        source.verify()
    identity = package_id or guid("package:" + target.stem)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=target.name + ".", suffix=".building", dir=target.parent
    )
    temp = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            _write(stream, assets, identity)
            stream.flush()
            os.fsync(stream.fileno())
        result = read_package(temp)
        require(
            result.id == identity and len(result.assets) == len(assets),
            "Output verification failed",
            "VERIFY_FAILED",
        )
        for original, copied in zip(assets, result.assets, strict=True):
            require(
                original.fingerprint() == copied.fingerprint(),
                "Payload verification failed",
                "VERIFY_FAILED",
                asset=original.name,
            )
        for source in sources:
            source.verify()
        # Recheck at commit time; exclusive hardlink creation prevents an output race.
        if overwrite:
            require(
                not any(same_path(target, Path(p)) for p in guards),
                "Output became a protected source",
                "PROTECTED_SOURCE",
            )
            os.replace(temp, target)
        else:
            try:
                os.link(temp, target)
            except FileExistsError as error:
                raise StudioError(
                    "OUTPUT_EXISTS", "Output was created by another process"
                ) from error
        return {
            "path": str(target),
            "package_id": str(identity),
            "assets": len(assets),
            "bytes": target.stat().st_size,
            "sha256": sha256_file(target),
            "structurally_verified": True,
            "engine_verified": False,
        }
    finally:
        temp.unlink(missing_ok=True)

"""Behavior tests use original synthetic data, never installed game files."""

import os
import struct
import uuid
from dataclasses import replace

import lz4.block
import pytest

from tpac_studio.core import Asset, Segment, read_package, write_package
from tpac_studio.demo import demo_assets
from tpac_studio.errors import StudioError
from tpac_studio.workspace import Workspace


@pytest.fixture
def package(tmp_path):
    path = tmp_path / "input.tpac"
    write_package(path, demo_assets())
    return path


def test_roundtrip(package, tmp_path):
    before = read_package(package)
    report = write_package(tmp_path / "copy.tpac", before.assets, package_id=before.id)
    after = read_package(report["path"])
    assert before.id == after.id
    assert [a.fingerprint() for a in before.assets] == [a.fingerprint() for a in after.assets]
    assert report["structurally_verified"] and not report["engine_verified"]


def test_independent_v1_container(tmp_path):
    """A manually assembled v1 table checks compatibility outside our v2 writer."""
    identity, kind, asset_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    name, metadata = b"original_v1", b"opaque_v1_metadata"
    table = kind.bytes_le + asset_id.bytes_le + struct.pack("<I", len(name)) + name
    table += struct.pack("<Q", len(metadata)) + metadata + bytes(8) + struct.pack("<II", 0, 0)
    source = tmp_path / "v1.tpac"
    source.write_bytes(
        struct.pack("<II", 0x43415054, 1)
        + identity.bytes_le
        + struct.pack("<III", 1, len(table), 0)
        + table
    )
    package = read_package(source)
    assert package.version == 1 and package.assets[0].version == 0
    target = tmp_path / "converted.tpac"
    write_package(target, package.assets)
    assert read_package(target).assets[0].fingerprint() == package.assets[0].fingerprint()


def test_failed_write_keeps_existing_output(tmp_path, monkeypatch):
    import tpac_studio.core as core

    target = tmp_path / "existing.tpac"
    target.write_bytes(b"original output")

    def fail(stream, assets, identity):
        stream.write(b"partial")
        raise OSError("simulated storage failure")

    monkeypatch.setattr(core, "_write", fail)
    with pytest.raises(OSError):
        write_package(target, demo_assets(), overwrite=True)
    assert target.read_bytes() == b"original output"
    assert not list(tmp_path.glob("*.building"))


def test_large_known_reference_index():
    workspace = Workspace()
    records = [Asset(f"item_{i}", uuid.uuid4(), uuid.uuid4(), b"") for i in range(150)]
    records[0] = replace(records[0], metadata=b"unaligned" + records[-1].id.bytes_le)
    workspace.add_assets(records)
    assert workspace.dependencies()["links"][str(records[0].id)] == [str(records[-1].id)]


@pytest.mark.parametrize("storage", [0, 1, 7])
def test_opaque_payloads(tmp_path, storage):
    raw = b"original opaque data" * 100
    data = lz4.block.compress(raw, store_size=False) if storage == 1 else raw
    identity = uuid.uuid4()
    asset = Asset(
        "opaque",
        uuid.uuid4(),
        identity,
        b"metadata",
        4,
        (Segment(identity, uuid.uuid4(), 9, 123, storage, data, actual_size=len(raw)),),
        uuid.uuid4().bytes_le * 3,
        b"checksum",
    )
    write_package(tmp_path / "a.tpac", [asset])
    loaded = read_package(tmp_path / "a.tpac")
    write_package(tmp_path / "b.tpac", loaded.assets)
    assert read_package(tmp_path / "b.tpac").assets[0].fingerprint() == asset.fingerprint()


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"TPAC",
        struct.pack("<II", 0x43415054, 9) + bytes(28),
        struct.pack("<II", 0x43415054, 2) + bytes(16) + struct.pack("<III", 999999999, 0, 0),
    ],
)
def test_reject_invalid(tmp_path, raw):
    path = tmp_path / "bad.tpac"
    path.write_bytes(raw)
    with pytest.raises(StudioError):
        read_package(path)


def test_original_and_hardlink_protected(package, tmp_path):
    assets = read_package(package).assets
    with pytest.raises(StudioError, match="original source"):
        write_package(package, assets, overwrite=True)
    alias = tmp_path / "alias.tpac"
    os.link(package, alias)
    with pytest.raises(StudioError, match="original source"):
        write_package(alias, assets, overwrite=True)


def test_metadata_only_source_protected(tmp_path):
    path = tmp_path / "metadata.tpac"
    write_package(path, [Asset("meta", uuid.uuid4(), uuid.uuid4())])
    with pytest.raises(StudioError, match="original source"):
        write_package(path, read_package(path).assets, overwrite=True)


def test_source_changes_abort(package, tmp_path):
    assets = read_package(package).assets
    with package.open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(StudioError, match="changed"):
        write_package(tmp_path / "bad.tpac", assets)
    assert not (tmp_path / "bad.tpac").exists()


def test_explicit_overwrite(package, tmp_path):
    target = tmp_path / "out.tpac"
    target.write_bytes(b"existing")
    with pytest.raises(StudioError):
        write_package(target, read_package(package).assets)
    assert target.read_bytes() == b"existing"


def test_workspace_conflict_atomic(package):
    w = Workspace()
    w.add_packages([str(package)])
    before = w.summary()
    a = w.assets[0]
    with pytest.raises(StudioError):
        w.add_assets([Asset("new", uuid.uuid4(), uuid.uuid4()), replace(a, metadata=b"changed")])
    assert w.summary() == before
    assert w.add_assets([a])["decisions"][0]["action"] == "identical"


def test_dependency_plan_and_undo(tmp_path):
    a, b, c = [Asset(n, uuid.uuid4(), uuid.uuid4()) for n in "abc"]
    a = replace(a, metadata=b.id.bytes_le)
    b = replace(b, metadata=c.id.bytes_le)
    w = Workspace()
    w.add_assets([a, b, c])
    w.select(["b", "c"], False)
    plan = w.plan()
    assert len(plan["auto_included"]) == 2
    w.remove(["c"])
    missing = w.plan()
    assert missing["missing_known_references"][0]["target_name"] == "c"
    with pytest.raises(StudioError):
        w.build(str(tmp_path / "blocked.tpac"), missing["plan_id"])
    w.undo()
    assert len(w.plan()["assets"]) == 3
    with pytest.raises(StudioError, match="Plan"):
        w.build(str(tmp_path / "stale.tpac"), plan["plan_id"])


def test_workspace_self_contained_and_concurrency(package, tmp_path):
    target = tmp_path / "work.tpstudio"
    w = Workspace()
    w.add_packages([str(package)])
    w.select([w.assets[0].name], False)
    w.save(target)
    with Workspace.open(target) as first, Workspace.open(target) as second:
        assert first.selected == w.selected and first.protected == w.protected
        first.select([first.assets[0].name], True)
        first.save(target)
        with pytest.raises(StudioError, match="another process"):
            second.save(target)
        package.unlink()
        p = first.plan()
        first.build(str(tmp_path / "from_saved.tpac"), p["plan_id"])


def test_empty_workspace_roundtrip(tmp_path):
    path = tmp_path / "empty.tpstudio"
    w = Workspace()
    w.save(path)
    with Workspace.open(path) as again:
        assert again.summary()["assets"] == 0

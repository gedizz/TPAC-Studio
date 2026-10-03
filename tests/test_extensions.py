"""Provider boundary tests exercise real edits, schema validation and identity guards."""

import importlib.util
from dataclasses import replace
from pathlib import Path

from tpac_studio.service import Studio


def provider():
    source = Path(__file__).resolve().parents[1] / "examples/extension/example_opacity.py"
    spec = importlib.util.spec_from_file_location("test_example", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ExampleOpacity()


def test_extension_edit():
    studio = Studio()
    studio.registry.register(provider())
    studio.examples_load()
    assert studio.extension_inspect("example-opacity", "demo_smoke") == {"emitters": 1}
    before = studio.workspace.get("demo_smoke").fingerprint()
    result = studio.execute(
        "extension_edit",
        {
            "provider": "example-opacity",
            "asset": "demo_smoke",
            "values": {"opacity": 0.5},
            "expected_revision": 1,
        },
    )
    assert result["ok"], result
    assert studio.workspace.get("demo_smoke").fingerprint() != before
    revision = studio.workspace.revision
    bad = studio.execute(
        "extension_edit",
        {"provider": "example-opacity", "asset": "demo_smoke", "values": {"opacity": 99}},
    )
    assert not bad["ok"] and studio.workspace.revision == revision
    studio.workspace_undo()
    assert studio.workspace.get("demo_smoke").fingerprint() == before


def test_provider_cannot_replace_identity():
    extension = provider()
    extension.edit = lambda record, values: replace(record, name="changed")
    studio = Studio()
    studio.registry.register(extension)
    studio.examples_load()
    result = studio.execute(
        "extension_edit",
        {"provider": "example-opacity", "asset": "demo_smoke", "values": {"opacity": 0.5}},
    )
    assert not result["ok"] and studio.workspace.revision == 1


def test_unknown_provider_and_non_json_result():
    studio = Studio()
    studio.examples_load()
    assert not studio.execute("extension_schema", {"provider": "not-installed"})["ok"]
    extension = provider()
    extension.inspect = lambda record: {"bad": float("nan")}
    studio.registry.register(extension)
    assert not studio.execute(
        "extension_inspect", {"provider": extension.name, "asset": "demo_smoke"}
    )["ok"]

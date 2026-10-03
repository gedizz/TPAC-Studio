"""Validate shared service contracts, edits, plugins and headless operation."""

import json
import subprocess
import sys

import pytest
from PIL import Image

from tpac_studio.core import read_package
from tpac_studio.demo import demo_assets, triangle_document
from tpac_studio.particles import particle_data
from tpac_studio.service import Studio, operation_schemas
from tpac_studio.textures import texture_image


def test_headless_import():
    command = 'from tpac_studio.service import Studio; import sys; assert not any(k.startswith(("PySide6", "OpenGL")) for k in sys.modules); print(Studio().capabilities()["api_version"])'
    result = subprocess.run([sys.executable, "-c", command], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_texture_and_particle_settings():
    studio = Studio()
    studio.workspace.add_assets(demo_assets())
    assert texture_image(studio.workspace.get("demo_checker")).size == (64, 64)
    before = particle_data(studio.workspace.get("demo_smoke"))
    response = studio.execute(
        "particle_edit",
        {"asset": "demo_smoke", "values": {"opacity": 0.5, "lifetime": 2}, "expected_revision": 1},
    )
    assert response["ok"], response
    after = particle_data(studio.workspace.get("demo_smoke"))
    assert after["emitters"][0]["alphas"][1][1] == pytest.approx(
        before["emitters"][0]["alphas"][1][1] * 0.5
    )
    assert after["emitters"][0]["p1"][4]["range"][0] == 5
    assert not studio.execute(
        "particle_edit", {"asset": "demo_smoke", "values": {}, "expected_revision": 1}
    )["ok"]
    studio.workspace.undo()
    assert particle_data(studio.workspace.get("demo_smoke")) == before


@pytest.mark.parametrize(
    "values",
    [
        {"invalid": 1},
        {"preview.fov": True},
        {"preview.fov": float("nan")},
        {"preview.fov": 1000},
        {"preview.loop": "true"},
    ],
)
def test_settings_reject_invalid(values):
    studio = Studio()
    response = studio.execute("settings_update", {"values": values})
    assert not response["ok"] and studio.workspace.revision == 0


def test_schema_rejects_extra_fields():
    studio = Studio()
    assert not studio.execute("build_plan", {"overwrite": True})["ok"]
    assert "scale" in operation_schemas()["model_import"]["properties"]


def test_model_json_import(tmp_path):
    source = tmp_path / "triangle.json"
    source.write_text(json.dumps(triangle_document()))
    studio = Studio()
    response = studio.execute("model_import", {"path": str(source), "name": "triangle"})
    assert response["ok"], response
    from tpac_studio.mesh_preview import mesh_parts, material_info

    mesh = studio.workspace.get("triangle")
    parts = mesh_parts(mesh)
    assert len(parts) == 1 and len(parts[0]["pos"]) == 3
    assert material_info(studio.workspace.get("triangle_part0_material"))["slots"]


def test_root_boundary(tmp_path):
    studio = Studio(root=str(tmp_path))
    assert (
        studio.execute("package_inspect", {"path": "../outside.tpac"})["error"]["code"]
        == "PATH_OUTSIDE_ROOT"
    )


def test_cli_end_to_end(tmp_path):
    image = tmp_path / "owned.png"
    Image.new("RGBA", (4, 4), "red").save(image)
    project = tmp_path / "test.tpstudio"

    def run(operation, arguments):
        p = subprocess.run(
            [
                sys.executable,
                "-m",
                "tpac_studio.cli",
                operation,
                "--workspace",
                str(project),
                "--args",
                json.dumps(arguments),
            ],
            capture_output=True,
            text=True,
        )
        result = json.loads(p.stdout)
        assert p.returncode == 0, (result, p.stderr)
        return result["result"]

    run("texture_import", {"path": str(image), "name": "owned"})
    plan = run("build_plan", {})
    output = tmp_path / "new.tpac"
    result = run("build_execute", {"output": str(output), "plan_id": plan["plan_id"]})
    assert result["structurally_verified"] and read_package(output).assets[0].name == "owned"


def test_optimized_python_still_validates(tmp_path):
    target = tmp_path / "bad.tpac"
    target.write_bytes(b"TPAC")
    p = subprocess.run(
        [
            sys.executable,
            "-O",
            "-m",
            "tpac_studio.cli",
            "package_inspect",
            "--args",
            json.dumps({"path": str(target)}),
        ],
        capture_output=True,
        text=True,
    )
    assert p.returncode == 2 and not json.loads(p.stdout)["ok"]

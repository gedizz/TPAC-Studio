"""Saved-project validation and rooted CLI regression cases."""

import json
import subprocess
import sys
import zipfile

import pytest

from tpac_studio.errors import StudioError
from tpac_studio.workspace import Workspace


def test_unexpected_workspace_member(tmp_path):
    path = tmp_path / "bad.tpstudio"
    workspace = Workspace()
    workspace.save(path)
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("../not-allowed", "data")
    with pytest.raises(StudioError, match="Unexpected"):
        Workspace.open(path)


def test_cli_root_relative_workspace_and_bom_request(tmp_path):
    workspace = Workspace()
    workspace.save(tmp_path / "saved.tpstudio")
    (tmp_path / "request.json").write_text(
        json.dumps({"values": {"preview.fov": 61}}), encoding="utf-8-sig"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tpac_studio.cli",
            "settings_update",
            "--root",
            str(tmp_path),
            "--workspace",
            "saved.tpstudio",
            "--request",
            "request.json",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    with Workspace.open(tmp_path / "saved.tpstudio") as reopened:
        assert reopened.settings["preview.fov"] == 61

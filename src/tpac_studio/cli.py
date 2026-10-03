"""Noninteractive JSON CLI. stdout is exclusively one result envelope."""

import argparse
import json
import sys
from pathlib import Path

from .service import API_VERSION, OPERATIONS, Studio
from .workspace import Workspace

MUTATIONS = {
    "package_add",
    "asset_select",
    "asset_remove",
    "workspace_undo",
    "settings_update",
    "particle_edit",
    "texture_import",
    "model_import",
    "examples_load",
    "extension_edit",
}


def main(argv: list[str] | None = None) -> int:
    """Run a documented operation; exit 0 on success, 2 on an operation failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=sorted(OPERATIONS))
    parser.add_argument(
        "--json", action="store_true", help="JSON is always used; explicit flag for scripts"
    )
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--args", default="{}", help="JSON arguments object")
    inputs.add_argument("--request", type=Path, help="UTF-8 JSON arguments file (max 4 MiB)")
    parser.add_argument(
        "--workspace", type=Path, help="Open this workspace; successful mutations are saved here"
    )
    parser.add_argument("--root", help="Optional permitted filesystem root")
    parser.add_argument("--blender", help="Trusted Blender executable for static imports")
    parser.add_argument(
        "--extension", action="append", default=[], help="Explicit trusted installed provider"
    )
    args = parser.parse_args(argv)
    studio = Studio(root=args.root, blender=args.blender)
    try:
        project = studio.path(str(args.workspace)) if args.workspace else None
        if project and project.exists():
            studio.workspace = Workspace.open(project)
        for extension in args.extension:
            studio.registry.load(extension)
        if args.request:
            request = studio.path(str(args.request))
            if request.stat().st_size > 4 * 1024**2:
                raise ValueError("Request file exceeds 4 MiB")
            values = json.loads(request.read_text(encoding="utf-8-sig"))
        else:
            values = json.loads(args.args)
        response = studio.execute(args.operation, values)
        if response["ok"] and args.workspace and args.operation in MUTATIONS:
            saved = studio.workspace.save(studio.path(str(args.workspace)))
            response["workspace_saved"] = saved["path"]
    except Exception as error:
        from .errors import StudioError

        response = {
            "api_version": API_VERSION,
            "ok": False,
            "error": error.as_dict()
            if isinstance(error, StudioError)
            else {"code": "INVALID_ARGUMENT", "message": str(error), "details": {}},
        }
    finally:
        studio.close()
    print(json.dumps(response, ensure_ascii=True, allow_nan=False))
    return 0 if response["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())

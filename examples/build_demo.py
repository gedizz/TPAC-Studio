"""Build original synthetic examples without needing a game installation.

Usage: python examples/build_demo.py --output local/demo
"""

import argparse
import json
from pathlib import Path

from tpac_studio.service import Studio


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("local/demo"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    studio = Studio(root=str(args.output))
    try:
        studio.examples_load()
        plan = studio.build_plan()
        (args.output / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf8")
        report = studio.build_execute("example.tpac", plan["plan_id"])
        studio.workspace_save("example.tpstudio")
        print(json.dumps(report, indent=2))
    finally:
        studio.close()


if __name__ == "__main__":
    main()

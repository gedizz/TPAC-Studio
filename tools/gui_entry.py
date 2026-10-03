"""Entry point for the optional local executable build."""

import sys
import traceback
from pathlib import Path


def run():
    """Record bootstrap failures for the explicit noninteractive desktop check."""
    try:
        from tpac_studio.gui import main

        main()
    except Exception:
        if "--check-startup" in sys.argv and "--output" in sys.argv:
            output = Path(sys.argv[sys.argv.index("--output") + 1])
            output.mkdir(parents=True, exist_ok=True)
            (output / "bootstrap-error.txt").write_text(traceback.format_exc(), encoding="utf8")
            raise SystemExit(1)
        raise


if __name__ == "__main__":
    run()

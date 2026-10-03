"""Exercise this application's real Qt/OpenGL widget using original examples.

Run manually on a desktop: python tools/check_gui.py --output local/gui-check.
This does not automate any other application or launch the game.
"""

import argparse
import json
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from tpac_studio.gui import Window, theme


def main(argv=None):
    """Open original previews briefly, record evidence, then close the test window."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    fmt = QSurfaceFormat()
    fmt.setVersion(2, 1)
    fmt.setProfile(QSurfaceFormat.CompatibilityProfile)
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication([])
    theme(app)
    window = Window()
    window.show()
    response = window.studio.execute("examples_load", {})
    if not response["ok"]:
        raise RuntimeError(response)
    window.refresh()
    steps = ["demo_checker", "demo_triangle", "demo_smoke"]
    results = []

    def step():
        if not steps:
            (args.output / "results.json").write_text(json.dumps(results, indent=2))
            window.dirty = False
            window.close()
            app.exit(1 if any(row["error"] or not row["gl"] for row in results) else 0)
            return
        name = steps.pop(0)
        for i in range(window.tree.topLevelItemCount()):
            item = window.tree.topLevelItem(i)
            if item.text(0) == name:
                window.tree.setCurrentItem(item)
                break
        window.timeline.setValue(120)

        def capture():
            window.view.grabFramebuffer().save(str(args.output / (name + "-viewport.png")))
            window.grab().save(str(args.output / (name + ".png")))
            particles = len(window.view._particles()) if name == "demo_smoke" else None
            error = window.view.error or (
                "No particles at the scrubbed time" if particles == 0 else ""
            )
            results.append(
                {
                    "name": name,
                    "error": error,
                    "gl": window.view.isValid(),
                    "particle_count": particles,
                }
            )
            QTimer.singleShot(50, step)

        QTimer.singleShot(600, capture)

    QTimer.singleShot(700, step)
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()

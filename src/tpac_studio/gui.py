"""Qt desktop adapter over Studio services. No game installation is required."""

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPalette, QSurfaceFormat
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .service import Studio
from .viewport import Viewport


def theme(app):
    """Use a readable neutral palette without system theme or mixer changes."""
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in (
        (QPalette.Window, "#141b25"),
        (QPalette.WindowText, "#d8e4ed"),
        (QPalette.Base, "#1b2531"),
        (QPalette.Text, "#d8e4ed"),
        (QPalette.Button, "#243344"),
        (QPalette.ButtonText, "#d8e4ed"),
        (QPalette.Highlight, "#23665e"),
        (QPalette.HighlightedText, "#ffffff"),
    ):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(
        'QWidget {font-family: "Segoe UI";font-size:12px;} QPushButton {padding:7px;} QLineEdit,QComboBox {padding:6px;} QToolBar {spacing:8px;padding:10px;} QTreeWidget::item {padding:5px;}'
    )


class Operation(QThread):
    """Execute one service call off the UI thread; report structured results."""

    result = Signal(object)

    def __init__(self, studio, name, arguments, parent):
        super().__init__(parent)
        self.studio = studio
        self.name = name
        self.arguments = arguments

    def run(self):
        self.result.emit(self.studio.execute(self.name, self.arguments))


class Window(QMainWindow):
    """Package explorer, workspace editor and build review frontend."""

    def __init__(self):
        super().__init__()
        self.studio = Studio()
        self.job = None
        self.dirty = False
        self.project = ""
        self.current = None
        self.setWindowTitle(f"TPAC Studio {__version__}")
        self.resize(1440, 900)
        self.toolbar = self.addToolBar("Workspace")
        self.toolbar.setMovable(False)
        for title, callback in [
            ("New", self.new),
            ("Open TPACs", self.open_packages),
            ("Import", self.import_asset),
            ("Save workspace", self.save),
            ("Open workspace", self.open_workspace),
            ("Build TPAC", self.build),
            ("Undo", lambda: self.run("workspace_undo")),
            ("Examples", lambda: self.run("examples_load")),
        ]:
            action = self.toolbar.addAction(title)
            action.triggered.connect(lambda _=False, fn=callback: fn())
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 12)
        self.setCentralWidget(widget)
        row = QHBoxLayout()
        row.addWidget(QLabel("<h2>TPAC Studio</h2>"))
        row.addStretch()
        self.count = QLabel("No assets")
        row.addWidget(self.count)
        layout.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)
        split = QSplitter()
        layout.addWidget(split, 1)
        library = QWidget()
        left = QVBoxLayout(library)
        left.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search name…")
        self.search.textChanged.connect(self.filter)
        left.addWidget(self.search)
        self.kind = QComboBox()
        self.kind.addItems(
            [
                "All types",
                "Mesh",
                "Texture",
                "Material",
                "Particle",
                "Animation",
                "Animation source",
                "Other",
            ]
        )
        self.kind.currentTextChanged.connect(self.filter)
        left.addWidget(self.kind)
        self.source = QComboBox()
        self.source.addItem("All packages", "")
        self.source.currentIndexChanged.connect(self.filter)
        left.addWidget(self.source)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Asset", "Type", "Source", "KiB"])
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setColumnWidth(0, 180)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 140)
        self.tree.currentItemChanged.connect(self.select)
        self.tree.itemChanged.connect(self.check_changed)
        left.addWidget(self.tree, 1)
        buttons = QHBoxLayout()
        for title, callback in [
            ("All", lambda: self.check_visible(True)),
            ("None", lambda: self.check_visible(False)),
            ("Remove", self.remove),
        ]:
            button = QPushButton(title)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        left.addLayout(buttons)
        split.addWidget(library)
        self.tabs = QTabWidget()
        self.view = Viewport()
        self.tabs.addTab(self.view, "Preview")
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.tabs.addTab(self.details, "Asset details")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.tabs.addTab(self.log, "Activity")
        middle = QWidget()
        ml = QVBoxLayout(middle)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.addWidget(self.tabs, 1)
        playback = QHBoxLayout()
        self.play = QCheckBox("Play")
        playback.addWidget(self.play)
        self.timeline = QSlider(Qt.Horizontal)
        self.timeline.setRange(0, 600)
        self.timeline.valueChanged.connect(self.scrub)
        playback.addWidget(self.timeline)
        ml.addLayout(playback)
        split.addWidget(middle)
        side = QWidget()
        right = QVBoxLayout(side)
        side.setMaximumWidth(280)
        self.title = QLabel("Select an asset")
        self.title.setWordWrap(True)
        right.addWidget(self.title)
        note = QLabel(
            "Inspect and repackage unknown records without decoding. Previews approximate supported content."
        )
        note.setWordWrap(True)
        right.addWidget(note)
        self.particle = QWidget()
        form = QFormLayout(self.particle)
        self.fields = {}
        for key in ("opacity", "size", "emission", "lifetime"):
            box = QDoubleSpinBox()
            box.setRange(0.05, 5)
            box.setSingleStep(0.05)
            box.setValue(1)
            form.addRow(key.title() + " ×", box)
            self.fields[key] = box
        apply = QPushButton("Apply particle settings")
        apply.clicked.connect(self.edit_particle)
        form.addRow(apply)
        right.addWidget(self.particle)
        self.particle.hide()
        fov = QDoubleSpinBox()
        fov.setRange(15, 100)
        fov.setValue(42)
        fov.valueChanged.connect(lambda value: self.preview_setting("preview.fov", value))
        right.addWidget(QLabel("Preview FOV (degrees)"))
        right.addWidget(fov)
        self.fov = fov
        export = QPushButton("Export current asset")
        export.clicked.connect(self.export)
        right.addWidget(export)
        screenshot = QPushButton("Save preview PNG")
        screenshot.clicked.connect(self.screenshot)
        right.addWidget(screenshot)
        right.addStretch()
        limitations = QLabel(
            "Animation records can be repackaged unchanged. Animation playback, rigging and authoring are not supported."
        )
        limitations.setWordWrap(True)
        right.addWidget(limitations)
        split.addWidget(side)
        split.setSizes([500, 660, 250])
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)
        self.setAcceptDrops(True)
        self.statusBar().showMessage("Ready • load procedural Examples or open your TPACs")

    def run(self, name, arguments=None, done=None):
        if self.job:
            return
        before = self.studio.workspace.revision
        self.toolbar.setEnabled(False)
        self.centralWidget().setEnabled(False)
        self.progress.show()
        self.job = Operation(self.studio, name, arguments or {}, self)

        def result(response):
            self.log.appendPlainText(json.dumps(response, indent=2))
            if not response["ok"]:
                QMessageBox.warning(self, "Operation failed", response["error"]["message"])
                return
            self.dirty = self.dirty or self.studio.workspace.revision != before
            self.refresh()
            if done:
                done(response["result"])

        self.job.result.connect(result)
        self.job.finished.connect(self.finished)
        self.job.start()

    def finished(self):
        self.toolbar.setEnabled(True)
        self.centralWidget().setEnabled(True)
        self.progress.hide()
        self.job.deleteLater()
        self.job = None

    def refresh(self):
        previous = self.current
        self.tree.blockSignals(True)
        self.tree.clear()
        for asset in sorted(self.studio.workspace.assets, key=lambda a: (a.type, a.name)):
            origin = self.studio.workspace.origins.get(asset.id, "authored")
            item = QTreeWidgetItem(
                [asset.name, asset.type, Path(origin).name, f"{asset.size / 1024:,.1f}"]
            )
            item.setData(0, Qt.UserRole, str(asset.id))
            item.setData(2, Qt.UserRole, origin)
            item.setToolTip(2, origin)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                0, Qt.Checked if asset.id in self.studio.workspace.selected else Qt.Unchecked
            )
            self.tree.addTopLevelItem(item)
        self.tree.blockSignals(False)
        origin = self.source.currentData()
        self.source.blockSignals(True)
        self.source.clear()
        self.source.addItem("All packages", "")
        for value in sorted(set(self.studio.workspace.origins.values())):
            self.source.addItem(Path(value).name, value)
        self.source.setCurrentIndex(max(0, self.source.findData(origin)))
        self.source.blockSignals(False)
        self.filter()
        self.count.setText(
            f"{len(self.studio.workspace.assets)} assets • revision {self.studio.workspace.revision}"
        )
        self.fov.blockSignals(True)
        self.fov.setValue(self.studio.workspace.settings["preview.fov"])
        self.fov.blockSignals(False)
        self.view.fov = self.fov.value()
        self.view.emitter_speed = self.studio.workspace.settings["preview.emitter_speed"]
        found = None
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item.data(0, Qt.UserRole) == previous:
                found = item
                break
        if found is None and self.tree.topLevelItemCount():
            found = self.tree.topLevelItem(0)
        if found:
            self.tree.setCurrentItem(found)
        else:
            self.current = None
            self.view.clear()
            self.view.label = "Select an asset"
            self.view.update()
            self.details.clear()
            self.particle.hide()

    def filter(self, *_args):
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            item.setHidden(
                self.search.text().casefold() not in item.text(0).casefold()
                or (
                    self.kind.currentText() != "All types"
                    and self.kind.currentText() != item.text(1)
                )
                or bool(
                    self.source.currentData()
                    and item.data(2, Qt.UserRole) != self.source.currentData()
                )
            )

    def select(self, item, *_args):
        if item is None:
            return
        self.current = item.data(0, Qt.UserRole)
        asset = self.studio.workspace.get(self.current)
        self.title.setText(asset.name)
        self.details.setPlainText(
            json.dumps(self.studio.execute("asset_inspect", {"asset": self.current}), indent=2)
        )
        self.view.select(asset, self.studio.workspace.assets)
        self.timeline.setValue(0)
        self.particle.setVisible(asset.type == "Particle")
        for field in self.fields.values():
            field.setValue(1)

    def check_changed(self, item, column):
        if column != 0:
            return
        response = self.studio.execute(
            "asset_select",
            {"assets": [item.data(0, Qt.UserRole)], "selected": item.checkState(0) == Qt.Checked},
        )
        if response["ok"]:
            self.dirty = True

    def check_visible(self, selected):
        ids = [
            self.tree.topLevelItem(i).data(0, Qt.UserRole)
            for i in range(self.tree.topLevelItemCount())
            if not self.tree.topLevelItem(i).isHidden()
        ]
        self.run("asset_select", {"assets": ids, "selected": selected})

    def discard(self):
        return (
            not self.dirty
            or QMessageBox.question(
                self,
                "Unsaved workspace",
                "Discard unsaved workspace edits?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            == QMessageBox.Yes
        )

    def new(self):
        if self.discard():
            self.run("workspace_new", done=lambda _: self.mark_saved(""))

    def mark_saved(self, path):
        self.project = path
        self.dirty = False

    def open_packages(self, paths=None):
        paths = (
            paths
            or QFileDialog.getOpenFileNames(self, "Open TPAC packages", "", "TPAC (*.tpac)")[0]
        )
        if not paths:
            return
        policy, ok = QInputDialog.getItem(
            self,
            "Duplicate policy",
            "If a GUID has different contents:",
            ["error", "keep", "replace"],
            0,
            False,
        )
        if ok:
            self.run("package_add", {"paths": paths, "conflict": policy})

    def save(self):
        path = QFileDialog.getSaveFileName(
            self,
            "Save self-contained workspace",
            self.project or "workspace.tpstudio",
            "TPAC Studio (*.tpstudio)",
        )[0]
        if not path:
            return
        if not path.endswith(".tpstudio"):
            path += ".tpstudio"
        self.run(
            "workspace_save",
            {"path": path, "overwrite": True},
            done=lambda _: self.mark_saved(path),
        )

    def open_workspace(self):
        if not self.discard():
            return
        path = QFileDialog.getOpenFileName(self, "Open workspace", "", "TPAC Studio (*.tpstudio)")[
            0
        ]
        if path:
            self.run("workspace_open", {"path": path}, done=lambda _: self.mark_saved(path))

    def remove(self):
        ids = [i.data(0, Qt.UserRole) for i in self.tree.selectedItems() if not i.isHidden()]
        if (
            ids
            and QMessageBox.question(
                self,
                "Remove assets",
                f"Remove {len(ids)} assets from this workspace? Originals remain untouched. Build review will report known missing links.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            self.run("asset_remove", {"assets": ids})

    def edit_particle(self):
        if self.current:
            self.run(
                "particle_edit",
                {
                    "asset": self.current,
                    "values": {key: widget.value() for key, widget in self.fields.items()},
                },
            )

    def preview_setting(self, name, value):
        response = self.studio.execute("settings_update", {"values": {name: value}})
        if response["ok"]:
            self.view.fov = value
            self.view.update()
            self.dirty = True

    def build(self):
        if not self.studio.workspace.assets:
            return
        include = (
            QMessageBox.question(
                self,
                "Available dependencies",
                "Include referenced assets available in this workspace?",
                QMessageBox.Yes | QMessageBox.No,
            )
            == QMessageBox.Yes
        )

        def review(plan):
            dialog = QDialog(self)
            dialog.setWindowTitle("Review exact build plan")
            dialog.resize(800, 620)
            layout = QVBoxLayout(dialog)
            text = QPlainTextEdit()
            text.setReadOnly(True)
            text.setPlainText(json.dumps(plan, indent=2))
            layout.addWidget(text)
            acknowledge = QCheckBox("I will provide listed missing assets separately")
            acknowledge.setVisible(bool(plan["missing_known_references"]))
            layout.addWidget(acknowledge)
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.button(QDialogButtonBox.Ok).setEnabled(
                bool(plan["assets"]) and not plan["missing_known_references"]
            )
            acknowledge.toggled.connect(
                lambda value: buttons.button(QDialogButtonBox.Ok).setEnabled(
                    bool(plan["assets"]) and value
                )
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            if dialog.exec() != QDialog.Accepted:
                return
            path = QFileDialog.getSaveFileName(
                self, "Build new TPAC", "my_assets.tpac", "TPAC (*.tpac)"
            )[0]
            if not path:
                return
            if not path.endswith(".tpac"):
                path += ".tpac"
            # Wait for the planning worker to finish before starting the build worker.
            arguments = {
                "output": path,
                "plan_id": plan["plan_id"],
                "include_dependencies": include,
                "allow_missing": acknowledge.isChecked(),
                "overwrite": True,
            }
            QTimer.singleShot(0, lambda: self.after_idle("build_execute", arguments))

        self.run("build_plan", {"include_dependencies": include}, review)

    def after_idle(self, name, arguments):
        if self.job:
            QTimer.singleShot(30, lambda: self.after_idle(name, arguments))
        else:
            self.run(name, arguments)

    def import_asset(self):
        path = QFileDialog.getOpenFileName(
            self,
            "Import image/static geometry",
            "",
            "Sources (*.png *.jpg *.jpeg *.tga *.dds *.json *.obj *.fbx *.glb *.gltf *.blend)",
        )[0]
        if not path:
            return
        name, ok = QInputDialog.getText(
            self, "Asset name", "Name for new asset:", text=Path(path).stem
        )
        if not ok:
            return
        image = Path(path).suffix.lower() in (".png", ".jpg", ".jpeg", ".tga", ".dds")
        if not image and Path(path).suffix.lower() != ".json" and not self.studio.blender:
            blender = QFileDialog.getOpenFileName(
                self, "Choose your trusted Blender executable", "", "Blender (blender.exe)"
            )[0]
            if not blender:
                return
            self.studio.blender = blender
        self.run("texture_import" if image else "model_import", {"path": path, "name": name})

    def export(self):
        if not self.current:
            return
        asset = self.studio.workspace.get(self.current)
        fmt = "png" if asset.type == "Texture" else "tpac"
        path = QFileDialog.getSaveFileName(
            self, "Export current asset", asset.name + "." + fmt, f"{fmt.upper()} (*.{fmt})"
        )[0]
        if path:
            self.run(
                "asset_export",
                {"asset": self.current, "output": path, "format": fmt, "overwrite": True},
            )

    def screenshot(self):
        path = QFileDialog.getSaveFileName(self, "Save preview", "preview.png", "PNG (*.png)")[0]
        if path:
            self.view.grabFramebuffer().save(path)

    def scrub(self, value):
        self.view.time = value / 100
        self.view.update()

    def tick(self):
        if self.play.isChecked() and self.view.emitters:
            value = self.timeline.value() + 3
            self.timeline.setValue(
                value % 601 if self.studio.workspace.settings["preview.loop"] else min(600, value)
            )

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths and all(path.lower().endswith(".tpac") for path in paths):
            self.open_packages(paths)

    def closeEvent(self, event):
        if self.job:
            event.ignore()
            return
        if not self.discard():
            event.ignore()
            return
        self.timer.stop()
        self.view.clear()
        self.studio.close()
        event.accept()


def main():
    """Launch the optional desktop application."""
    if "--check-startup" in sys.argv:
        from .desktop_check import main as check

        return check([arg for arg in sys.argv[1:] if arg != "--check-startup"])
    fmt = QSurfaceFormat()
    fmt.setVersion(2, 1)
    fmt.setProfile(QSurfaceFormat.CompatibilityProfile)
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication(sys.argv)
    theme(app)
    window = Window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

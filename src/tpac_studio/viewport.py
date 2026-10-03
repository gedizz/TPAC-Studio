"""Optional independent OpenGL preview; this does not embed the Bannerlord engine."""

import math
import uuid

import numpy as np
from OpenGL import GL as gl
from OpenGL.GLU import gluLookAt, gluPerspective
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from .mesh_preview import material_info, mesh_parts
from .particles import particle_data
from .textures import texture_image


class Viewport(QOpenGLWidget):
    """Orbitable static meshes, textures and approximate particle sprites."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(380, 300)
        self.setFocusPolicy(Qt.StrongFocus)
        self.assets = {}
        self.parts = []
        self.emitters = []
        self.picture = None
        self.label = "Open a package or load the procedural examples"
        self.error = ""
        self.yaw, self.pitch, self.distance = 45.0, 22.0, 4.0
        self.target = np.array([0.0, 0.0, 0.0])
        self.time = 0.0
        self.duration = 6.0
        self.fov = 42.0
        self.emitter_speed = 0.0
        self.last_mouse = None
        self.textures = {}

    def clear(self):
        """Clear active content and GPU texture cache while retaining camera settings."""
        if self.isValid():
            self.makeCurrent()
            if self.textures:
                gl.glDeleteTextures(list(self.textures.values()))
            self.doneCurrent()
        self.textures.clear()
        self.parts, self.emitters, self.picture = [], [], None
        self.error = ""
        self.time = 0

    def select(self, asset, assets):
        """Load supported content, displaying unsupported formats as an honest message."""
        self.clear()
        self.assets = {a.id: a for a in assets}
        self.label = asset.name
        try:
            if asset.type == "Mesh":
                self.parts = mesh_parts(asset)
                if self.parts:
                    points = np.concatenate([p["pos"] for p in self.parts])
                    if len(points):
                        low, high = points.min(0), points.max(0)
                        self.target = (low + high) / 2
                        self.distance = max(0.3, float(np.linalg.norm(high - low)) * 1.6)
            elif asset.type == "Texture":
                self.picture = texture_image(asset)
            elif asset.type == "Material":
                info = material_info(asset)
                target = self.assets.get(info["slots"].get(0))
                if target:
                    self.picture = texture_image(target)
                else:
                    self.error = "Open the material's albedo texture package to preview it."
            elif asset.type == "Particle":
                self.emitters = particle_data(asset)["emitters"]
                self.target = np.array([0.0, 0.0, 0.7])
                self.distance = 6
            else:
                self.error = (
                    "Opaque asset: inspect and repackage available; this build has no decoder."
                )
        except Exception as error:
            self.error = str(error)
        self.update()

    def _camera(self):
        yaw, pitch = math.radians(self.yaw), math.radians(self.pitch)
        direction = np.array(
            [math.cos(pitch) * math.sin(yaw), -math.cos(pitch) * math.cos(yaw), math.sin(pitch)]
        )
        eye = self.target + direction * self.distance
        right = np.cross(-direction, [0, 0, 1])
        right /= np.linalg.norm(right)
        up = np.cross(right, -direction)
        return eye, right, up

    def _texture(self, identity):
        if identity in self.textures:
            return self.textures[identity]
        asset = self.assets.get(identity)
        if asset is None:
            return 0
        try:
            image = texture_image(asset).transpose(
                __import__("PIL.Image", fromlist=["Transpose"]).Transpose.FLIP_TOP_BOTTOM
            )
            texture = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D,
                0,
                gl.GL_RGBA,
                image.width,
                image.height,
                0,
                gl.GL_RGBA,
                gl.GL_UNSIGNED_BYTE,
                image.tobytes(),
            )
            self.textures[identity] = texture
            return texture
        except Exception:
            return 0

    def _particles(self):
        particles = []
        for emitter_index, emitter in enumerate(self.emitters):
            material = self.assets.get(uuid.UUID(emitter["guids"][3]))
            sprite_texture = material_info(material)["slots"].get(0) if material else None
            columns, rows = (max(1, min(256, n)) for n in emitter["sprite"])
            life = max(0.01, min(30, emitter["p1"][4]["range"][0]))
            rate = max(0, min(1000, emitter["p2"][0]["range"][0]))
            delay = max(0, emitter["pre"][2])
            if self.time < delay:
                continue
            burst = "emit_at_once" in emitter["flags"]
            count = int(rate if burst else (self.time - delay) * rate)
            for index in range(max(0, count - 500), count):
                birth = delay if burst else index / max(1, rate) + delay
                age = self.time - birth
                if not 0 <= age < life:
                    continue
                # Stable hash-based seeds make scrubbing deterministic.
                random = np.mod(
                    np.sin((index + 1 + emitter_index * 173) * 12.9898 + np.arange(4) * 78.233)
                    * 43758.5453,
                    1,
                )
                velocity = np.array([p["range"][0] for p in emitter["p2"][1:4]]) + (
                    random[:3] * 2 - 1
                ) * np.array([abs(p["range"][1]) for p in emitter["p2"][1:4]])
                position = (
                    (random[:3] - 0.5) * 0.1
                    + velocity * age
                    + 0.5 * np.array(emitter["vectors"][16:19]) * age * age
                )
                position[0] += math.sin(age * 2 + index) * emitter["p2"][5]["range"][0] * age * 0.25
                if "emit_while_moving" in emitter["flags"]:
                    position[1] += birth * self.emitter_speed
                u = age / life
                alpha = (
                    float(
                        np.interp(
                            u, [x[0] for x in emitter["alphas"]], [x[1] for x in emitter["alphas"]]
                        )
                    )
                    if emitter["alphas"]
                    else 1
                )
                curve = emitter["curves"][1]
                size = max(0.005, curve["default"] * curve["multiplier"] * (1 + u))
                color = (
                    [
                        float(
                            np.interp(
                                u,
                                [x[0] for x in emitter["colors"]],
                                [x[j] for x in emitter["colors"]],
                            )
                        )
                        for j in (1, 2, 3)
                    ]
                    if emitter["colors"]
                    else [0.8] * 3
                )
                frame = int(max(0, age * emitter["sprite_animation"][1])) % (columns * rows)
                particles.append(
                    (position, size, alpha, color, sprite_texture, columns, rows, frame)
                )
        return particles[:1500]

    def paintGL(self):
        try:
            # QPainter changes GL state; restore it every frame before drawing 3D.
            gl.glUseProgram(0)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
            gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, 0)
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthFunc(gl.GL_LEQUAL)
            gl.glDepthMask(True)
            gl.glDisable(gl.GL_BLEND)
            gl.glDisable(gl.GL_CULL_FACE)
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glDisable(gl.GL_STENCIL_TEST)
            gl.glDisable(gl.GL_ALPHA_TEST)
            gl.glDisable(gl.GL_COLOR_LOGIC_OP)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBlendEquation(gl.GL_FUNC_ADD)
            gl.glShadeModel(gl.GL_SMOOTH)
            gl.glColorMask(True, True, True, True)
            gl.glDisable(gl.GL_TEXTURE_2D)
            gl.glDisable(gl.GL_LIGHTING)
            gl.glViewport(
                0,
                0,
                int(self.width() * self.devicePixelRatio()),
                int(self.height() * self.devicePixelRatio()),
            )
            gl.glClearColor(0.075, 0.09, 0.12, 1)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            gl.glMatrixMode(gl.GL_PROJECTION)
            gl.glLoadIdentity()
            gluPerspective(self.fov, max(0.1, self.width() / max(1, self.height())), 0.01, 5000)
            gl.glMatrixMode(gl.GL_MODELVIEW)
            gl.glLoadIdentity()
            eye, right, up = self._camera()
            gluLookAt(*eye, *self.target, 0, 0, 1)
            gl.glBegin(gl.GL_LINES)
            gl.glColor3f(0.16, 0.21, 0.27)
            for x in range(-10, 11):
                gl.glVertex3f(x, -10, 0)
                gl.glVertex3f(x, 10, 0)
                gl.glVertex3f(-10, x, 0)
                gl.glVertex3f(10, x, 0)
            gl.glEnd()
            for part in self.parts:
                if part["lod"] != min(p["lod"] for p in self.parts):
                    continue
                material = self.assets.get(part["material"])
                texture = 0
                if material:
                    texture = self._texture(material_info(material)["slots"].get(0))
                if texture:
                    gl.glEnable(gl.GL_TEXTURE_2D)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
                gl.glBegin(gl.GL_TRIANGLES)
                for index in part["indices"]:
                    normal = part["normal"][index]
                    light = max(0.3, min(1, 0.6 + float(np.dot(normal, [0.2, -0.3, 0.7])) * 0.4))
                    gl.glColor3f(light, light, light)
                    gl.glTexCoord2fv(part["uv"][index])
                    gl.glVertex3fv(part["pos"][index])
                gl.glEnd()
                gl.glDisable(gl.GL_TEXTURE_2D)
            gl.glEnable(gl.GL_BLEND)
            # Keep the widget framebuffer opaque; Qt composites it premultiplied.
            gl.glBlendFuncSeparate(
                gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA
            )
            gl.glDepthMask(False)
            for position, size, alpha, color, sprite, columns, rows, frame in sorted(
                self._particles(), key=lambda p: -np.linalg.norm(p[0] - eye)
            ):
                texture = self._texture(sprite) if sprite else 0
                if texture:
                    gl.glEnable(gl.GL_TEXTURE_2D)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
                    col, row = frame % columns, frame // columns
                    gl.glColor4f(*color, max(0, min(1, alpha)))
                    gl.glBegin(gl.GL_QUADS)
                    for x, y, u, v in ((-1, -1, 0, 0), (1, -1, 1, 0), (1, 1, 1, 1), (-1, 1, 0, 1)):
                        gl.glTexCoord2f((col + u) / columns, 1 - (row + 1 - v) / rows)
                        gl.glVertex3fv(position + (right * x + up * y) * size)
                    gl.glEnd()
                    gl.glDisable(gl.GL_TEXTURE_2D)
                    continue
                # Procedural radial sprite: the preview never needs a game smoke texture.
                gl.glBegin(gl.GL_TRIANGLE_FAN)
                gl.glColor4f(*color, alpha * 0.7)
                gl.glVertex3fv(position)
                for i in range(17):
                    angle = i * math.tau / 16
                    gl.glColor4f(*color, 0)
                    gl.glVertex3fv(
                        position + (right * math.cos(angle) + up * math.sin(angle)) * size
                    )
                gl.glEnd()
            gl.glDepthMask(True)
            gl.glDisable(gl.GL_BLEND)
            painter = QPainter(self)
            painter.setPen(QColor("#d8e4ed"))
            painter.drawText(16, 25, self.label)
            if self.picture is not None:
                image = self.picture.convert("RGBA")
                qimage = QImage(
                    image.tobytes(), image.width, image.height, QImage.Format_RGBA8888
                ).copy()
                scaled = qimage.scaled(
                    self.width() - 40,
                    self.height() - 100,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                painter.drawImage(
                    (self.width() - scaled.width()) // 2,
                    (self.height() - scaled.height()) // 2,
                    scaled,
                )
            if self.error:
                painter.drawText(
                    self.rect().adjusted(25, 45, -25, -40),
                    Qt.AlignCenter | Qt.TextWordWrap,
                    self.error,
                )
            painter.setPen(QColor("#9caabc"))
            painter.drawText(
                16,
                self.height() - 16,
                "Orbit: left drag • Pan: right drag • Zoom: wheel • Approximate preview",
            )
            painter.end()
        except Exception as error:
            self.error = str(error)

    def mousePressEvent(self, event):
        self.last_mouse = event.position()

    def mouseMoveEvent(self, event):
        if self.last_mouse is None:
            return
        delta = event.position() - self.last_mouse
        self.last_mouse = event.position()
        if event.buttons() & Qt.LeftButton:
            self.yaw += delta.x() * 0.4
            self.pitch = max(-85, min(85, self.pitch + delta.y() * 0.4))
        elif event.buttons() & Qt.RightButton:
            _, right, up = self._camera()
            self.target += (
                (-right * delta.x() + up * delta.y()) * self.distance / max(300, self.height())
            )
        self.update()

    def wheelEvent(self, event):
        self.distance = max(
            0.05, min(500, self.distance * math.exp(-event.angleDelta().y() / 1000))
        )
        self.update()

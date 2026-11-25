"""Panda3D desktop interface and animated cube playback."""

from __future__ import annotations

import math
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor

from direct.gui.DirectGui import DirectButton, DirectFrame
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import (
    AmbientLight,
    AntialiasAttrib,
    ClockObject,
    DirectionalLight,
    NodePath,
    Quat,
    TextNode,
    loadPrcFileData,
)

from rubiks_cube.cube import FACES, NORMALS, Cube, Move, Vec, scramble
from rubiks_cube.mesh import COLORS, body, tile, world
from rubiks_cube.solver import solve

INK = (0.90, 0.94, 1.0, 1)
MUTED = (0.58, 0.67, 0.79, 1)
TEAL = (0.42, 0.94, 0.80, 1)
PANEL = (0.065, 0.09, 0.15, 1)
BUTTON = (0.13, 0.18, 0.27, 1)
DEFAULT_ORBIT = (33.0, 25.0, 9.7)


class CubeApp(ShowBase):
    def __init__(self, window_type: str | None = None) -> None:
        super().__init__(windowType=window_type)
        self.disableMouse()
        self.setBackgroundColor(0.033, 0.047, 0.078)
        self.render.setAntialias(AntialiasAttrib.MAuto)
        self.camLens.setFov(39)
        self.camLens.setNearFar(0.1, 60)
        self.yaw, self.pitch, self.distance = DEFAULT_ORBIT
        self.dragging = False
        self.last_mouse: tuple[float, float] | None = None
        self._camera()
        self.accept("aspectRatioChanged", self._camera)

        ambient = AmbientLight("ambient")
        ambient.setColor((0.46, 0.49, 0.55, 1))
        self.render.setLight(self.render.attachNewNode(ambient))
        for name, color, hpr in (
            ("key", (0.78, 0.75, 0.70, 1), (-32, -42, 0)),
            ("fill", (0.33, 0.39, 0.55, 1), (150, -30, 0)),
        ):
            light = DirectionalLight(name)
            light.setColor(color)
            node = self.render.attachNewNode(light)
            node.setHpr(*hpr)
            self.render.setLight(node)

        self.cube = Cube()
        self.root = self.render.attachNewNode("cube")
        self.plastic = NodePath(body())
        self.tiles = {normal: NodePath(tile(normal)) for normal in NORMALS.values()}
        self.models: dict[Vec, NodePath] = {}
        self._rebuild()

        self.moves: deque[Move] = deque()
        self.active: Move | None = None
        self.pivot: NodePath | None = None
        self.elapsed = 0.0
        self.batch: str | None = None
        self.total = 0
        self.completed = 0
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cube-solver")
        self.solution: Future[list[Move]] | None = None
        self._ui()
        self._bindings()
        self.taskMgr.add(self._tick, "animate-cube")

    def _rebuild(self) -> None:
        for child in self.root.getChildren():
            child.removeNode()
        self.models.clear()
        for position, stickers in self.cube.pieces.items():
            node = self.root.attachNewNode(f"cubie-{position}")
            node.setPos(world(position))
            self.plastic.copyTo(node).setColor(0.026, 0.031, 0.043, 1)
            for normal, face in stickers.items():
                self.tiles[normal].copyTo(node).setColor(*COLORS[face])
            self.models[position] = node

    def _camera(self) -> None:
        yaw, pitch = math.radians(self.yaw), math.radians(self.pitch)
        radius = self.distance * math.cos(pitch)
        self.camera.setPos(radius * math.sin(yaw), -radius * math.cos(yaw),
                           self.distance * math.sin(pitch))
        self.camera.lookAt(0, 0, 0)
        # Leave room for the control panel on the left and sequence strip below.
        width, height = self.camLens.getFilmSize()
        self.camLens.setFilmOffset(-width * 0.112, -height * 0.032)

    def _orbit(self, yaw: float, pitch: float) -> None:
        self.yaw = (self.yaw + yaw) % 360
        self.pitch = max(-85, min(85, self.pitch + pitch))
        self._camera()

    def _zoom(self, amount: float) -> None:
        self.distance = max(7.5, min(18, self.distance + amount))
        self._camera()

    def _drag(self, enabled: bool) -> None:
        self.dragging = enabled
        self.last_mouse = None

    @staticmethod
    def _text(parent: NodePath, text: str, x: float, y: float, size: float,
              color: tuple[float, float, float, float] = INK) -> TextNode:
        label = TextNode(text or "label")
        label.setText(text)
        label.setTextColor(*color)
        label.setShadow(0.028, 0.028)
        label.setShadowColor(0, 0, 0, 0.35)
        node = parent.attachNewNode(label)
        node.setPos(x, 0, y)
        node.setScale(size)
        return label

    def _ui(self) -> None:
        panel = DirectFrame(parent=self.a2dTopLeft, pos=(0.055, 0, -0.07),
                            frameColor=PANEL, frameSize=(0, 0.73, -1.62, 0))
        self._text(panel, "PYTHON / PUZZLE LAB", 0.057, -0.101, 0.038, TEAL)
        self._text(panel, "Rubik's Cube", 0.052, -0.215, 0.092)
        self._text(panel, "3D SIMULATOR", 0.057, -0.301, 0.052, MUTED)
        self._text(panel, "FACE TURNS", 0.057, -0.435, 0.041)
        for index, face in enumerate(FACES):
            row, column = divmod(index, 3)
            x, y = 0.148 + column * 0.215, -0.535 - row * 0.119
            for offset, turns in ((-0.044, 1), (0.047, -1)):
                move = Move(face, turns)
                DirectButton(parent=panel, pos=(x + offset, 0, y), text=str(move),
                             text_scale=0.043, text_fg=COLORS[face], text_pos=(0, -0.015),
                             frameColor=BUTTON, frameSize=(-0.042, 0.042, -0.043, 0.043),
                             relief=1, command=self._manual, extraArgs=[move])
        self._text(panel, "Shift + face key reverses the turn", 0.057, -0.782, 0.031, MUTED)
        for index, (text, action, color, foreground) in enumerate((
            ("Scramble  /  Space", self._scramble, BUTTON, INK),
            ("Auto-solve  /  Enter", self._solve, TEAL, (0.04, 0.13, 0.17, 1)),
            ("Reset  /  Backspace", self._reset, BUTTON, INK),
        )):
            DirectButton(parent=panel, pos=(0.365, 0, -0.89 - index * 0.144), text=text,
                         text_scale=0.048, text_fg=foreground, text_pos=(0, -0.016),
                         frameColor=color, frameSize=(-0.307, 0.307, -0.055, 0.055),
                         relief=1, command=action)
        self._text(panel, "CAMERA", 0.057, -1.352, 0.038, TEAL)
        self._text(panel, "Drag or use arrow keys to orbit\nScroll to zoom", 0.057, -1.428,
                   0.038, MUTED)

        footer = DirectFrame(parent=self.a2dBottomLeft, pos=(0.055, 0, 0.047),
                             frameColor=PANEL, frameSize=(0, 1.87, 0, 0.22))
        self.status = self._text(footer, "SOLVED  /  Make a turn or scramble", 0.052, 0.135,
                                 0.047, TEAL)
        self.sequence = self._text(footer, "", 0.052, 0.052, 0.039, MUTED)
        self.sequence.setWordwrap(45)

    def _bindings(self) -> None:
        for face in FACES:
            self.accept(face.lower(), self._manual, [Move(face)])
            self.accept(f"shift-{face.lower()}", self._manual, [Move(face, -1)])
        for event, action in (("space", self._scramble), ("enter", self._solve),
                              ("backspace", self._reset), ("escape", self.userExit)):
            self.accept(event, action)
        for key, yaw, pitch in (("left", -8, 0), ("right", 8, 0),
                                ("up", 0, 8), ("down", 0, -8)):
            for suffix in ("", "-repeat"):
                self.accept(f"arrow_{key}{suffix}", self._orbit, [yaw, pitch])
        self.accept("wheel_up", self._zoom, [-0.6])
        self.accept("wheel_down", self._zoom, [0.6])
        self.accept("mouse1", self._drag, [True])
        self.accept("mouse1-up", self._drag, [False])

    def _manual(self, move: Move) -> None:
        if self.batch is None and self.solution is None and len(self.moves) < 40:
            self.moves.append(move)
            self.sequence.setText("")

    def _busy(self) -> bool:
        return bool(self.active or self.moves or self.solution)

    def _enqueue(self, moves: list[Move], batch: str) -> None:
        self.batch = batch
        self.total = len(moves)
        self.completed = 0
        self.moves.extend(moves)
        self.status.setText(f"{batch}  /  {self.total} moves")
        self.sequence.setText(" ".join(map(str, moves)))

    def _scramble(self) -> None:
        if not self._busy():
            self._enqueue(scramble(), "SCRAMBLE")

    def _solve(self) -> None:
        if self._busy():
            return
        if self.cube.is_solved:
            self.status.setText("SOLVED  /  Already solved")
            self.sequence.setText("")
            return
        self.solution = self.executor.submit(solve, self.cube.facelets())
        self.status.setText("SOLVING  /  Computing moves...")
        self.sequence.setText("")

    def _reset(self) -> None:
        if self.solution is not None:
            self.solution.cancel()
        self.solution = None
        self.moves.clear()
        self.active = self.pivot = None
        self.batch = None
        self.elapsed = 0.0
        self.cube = Cube()
        self.yaw, self.pitch, self.distance = DEFAULT_ORBIT
        self._drag(False)
        self._rebuild()
        self._camera()
        self.status.setText("SOLVED  /  Cube reset")
        self.sequence.setText("")

    def _advance(self, dt: float) -> None:
        if self.solution is not None and self.solution.done():
            future, self.solution = self.solution, None
            try:
                moves = future.result()
            except Exception as error:
                self.status.setText("SOLVER ERROR  /  Unable to compute a solution")
                print(f"Solver error: {error}")
            else:
                self._enqueue(moves, "SOLUTION")

        if self.active is None and self.moves:
            self.active = self.moves.popleft()
            self.pivot = self.root.attachNewNode("turn-pivot")
            self.elapsed = 0.0
            for position, node in self.models.items():
                if self.active.affects(position):
                    node.reparentTo(self.pivot)
            label = (f"{self.batch}  /  {self.completed + 1} of {self.total}"
                     if self.batch else "TURN")
            self.status.setText(f"{label}  /  {self.active}")
        if self.active is None or self.pivot is None:
            return
        self.elapsed += dt
        duration = {"SCRAMBLE": 0.112, "SOLUTION": 0.22}.get(self.batch or "", 0.19)
        progress = min(1.0, self.elapsed / duration)
        eased = progress * progress * (3 - 2 * progress)
        rotation = Quat()
        rotation.setFromAxisAngle(-90 * self.active.turns * eased, world(self.active.axis))
        self.pivot.setQuat(rotation)
        if progress >= 1:
            last = self.active
            self.cube.apply(last)
            self._rebuild()
            self.active = self.pivot = None
            self.completed += 1
            if not self.moves:
                solved = self.cube.is_solved
                if self.batch == "SOLUTION":
                    message = (f"SOLVED  /  {self.total} moves" if solved
                               else "SOLVER ERROR  /  Cube is not solved")
                elif self.batch == "SCRAMBLE":
                    message = "SCRAMBLED  /  Make a turn or auto-solve"
                else:
                    message = f"{'SOLVED' if solved else 'READY'}  /  Last turn: {last}"
                self.status.setText(message)
                self.batch = None

    def _tick(self, task: Task.Task) -> int:
        watcher = self.mouseWatcherNode
        if self.dragging and watcher is not None and watcher.hasMouse():
            mouse = watcher.getMouse()
            if self.last_mouse is not None:
                x, y = self.last_mouse
                self._orbit((x - mouse.x) * 125, (mouse.y - y) * 95)
            self.last_mouse = mouse.x, mouse.y
        else:
            self.last_mouse = None
        self._advance(ClockObject.getGlobalClock().getDt())
        return task.cont

    def destroy(self) -> None:
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()


def main() -> None:
    loadPrcFileData("", """
        window-title Rubik's Cube 3D
        win-size 1160 760
        framebuffer-multisample 1
        multisamples 4
        sync-video 1
    """)
    app = CubeApp()
    try:
        app.run()
    finally:
        app.destroy()

"""Exact integer-space model of a 3x3x3 cube (X right, Y up, Z front)."""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field

Vec = tuple[int, int, int]
FACES = "URFDLB"
NORMALS: dict[str, Vec] = {
    "U": (0, 1, 0), "R": (1, 0, 0), "F": (0, 0, 1),
    "D": (0, -1, 0), "L": (-1, 0, 0), "B": (0, 0, -1),
}
UP: dict[str, Vec] = dict.fromkeys(FACES, (0, 1, 0))
UP.update(U=(0, 0, -1), D=(0, 0, 1))
POSITIONS: tuple[Vec, ...] = tuple(
    (x, y, z) for x, y, z in itertools.product(range(-1, 2), repeat=3) if x or y or z
)
SOLVED = "".join(face * 9 for face in FACES)


def dot(a: Vec, b: Vec) -> int:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def rotate(vector: Vec, axis: Vec, quarters: int) -> Vec:
    for _ in range(quarters % 4):
        along = dot(axis, vector)
        x, y, z = cross(axis, vector)
        vector = (x + along * axis[0], y + along * axis[1], z + along * axis[2])
    return vector


@dataclass(frozen=True)
class Move:
    face: str
    turns: int = 1  # Clockwise when looking at the face.

    def __post_init__(self) -> None:
        if self.face not in NORMALS or self.turns not in (1, -1, 2):
            raise ValueError(f"Invalid face turn: {self.face!r}, {self.turns!r}")

    @property
    def axis(self) -> Vec:
        return NORMALS[self.face]

    def affects(self, position: Vec) -> bool:
        return dot(position, self.axis) == 1

    def inverse(self) -> Move:
        return Move(self.face, 2 if self.turns == 2 else -self.turns)

    def __str__(self) -> str:
        return self.face + {1: "", -1: "'", 2: "2"}[self.turns]

    @classmethod
    def parse(cls, token: str) -> Move:
        suffixes = {"": 1, "'": -1, "2": 2}
        if not token or token[1:] not in suffixes:
            raise ValueError(f"Invalid move notation: {token!r}")
        return cls(token[0], suffixes[token[1:]])


def solved_pieces() -> dict[Vec, dict[Vec, str]]:
    return {p: {n: f for f, n in NORMALS.items() if dot(p, n) == 1} for p in POSITIONS}


@dataclass
class Cube:
    pieces: dict[Vec, dict[Vec, str]] = field(default_factory=solved_pieces)

    def apply(self, move: Move) -> None:
        axis, quarters = move.axis, -move.turns
        after = {}
        for p, stickers in self.pieces.items():
            if move.affects(p):
                after[rotate(p, axis, quarters)] = {
                    rotate(n, axis, quarters): color for n, color in stickers.items()
                }
            else:
                after[p] = stickers
        self.pieces = after

    def facelets(self) -> str:
        """Serialize in Kociemba's URFDLB order, row by row from outside each face."""
        result: list[str] = []
        for face in FACES:
            normal, up = NORMALS[face], UP[face]
            right = cross(up, normal)
            positions = sorted(
                (p for p in POSITIONS if dot(p, normal) == 1),
                key=lambda p: (-dot(p, up), dot(p, right)),
            )
            result.extend(self.pieces[p][normal] for p in positions)
        return "".join(result)

    @property
    def is_solved(self) -> bool:
        return self.facelets() == SOLVED


def scramble(length: int = 24, rng: random.Random | None = None) -> list[Move]:
    """Generate random legal turns, avoiding adjacent turns on the same axis."""
    rng = rng if rng is not None else random.Random()
    moves: list[Move] = []
    for _ in range(length):
        candidates = [f for f in FACES if not moves or not dot(NORMALS[f], moves[-1].axis)]
        moves.append(Move(rng.choice(candidates), rng.choice([1, -1, 2])))
    return moves

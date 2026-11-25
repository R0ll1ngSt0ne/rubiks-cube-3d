"""Compute a solution from the current stickers, independent of move history."""

import kociemba

from rubiks_cube.cube import SOLVED, Move


def solve(facelets: str) -> list[Move]:
    if facelets == SOLVED:
        return []
    return [Move.parse(token) for token in kociemba.solve(facelets).split()]

import random
from collections import Counter

import pytest

from rubiks_cube.cube import FACES, SOLVED, Cube, Move, dot, scramble
from rubiks_cube.solver import solve


@pytest.mark.parametrize("face", FACES)
def test_turn_group(face: str) -> None:
    cube = Cube()
    turn = Move(face)
    cube.apply(turn)
    assert not cube.is_solved
    cube.apply(turn.inverse())
    assert cube.is_solved
    for _ in range(4):
        cube.apply(turn)
    assert cube.is_solved
    for _ in range(2):
        cube.apply(Move(face, 2))
    assert cube.is_solved


def test_standard_front_turn_facelets() -> None:
    cube = Cube()
    cube.apply(Move("F"))
    assert cube.facelets() == (
        "UUUUUULLL" "URRURRURR" "FFFFFFFFF" "RRRDDDDDD" "LLDLLDLLD" "BBBBBBBBB"
    )


@pytest.mark.parametrize("token", ["U", "R'", "F2", "D2", "L", "B'"])
def test_notation_round_trip(token: str) -> None:
    assert str(Move.parse(token)) == token


@pytest.mark.parametrize("token", ["", "Q", "R3", "R2'", "FF", "u"])
def test_bad_notation(token: str) -> None:
    with pytest.raises(ValueError):
        Move.parse(token)


@pytest.mark.parametrize("seed", range(8))
def test_solve_scrambled_facelets(seed: int) -> None:
    cube = Cube()
    moves = scramble(rng=random.Random(seed))
    assert len(moves) == 24
    assert all(dot(a.axis, b.axis) == 0 for a, b in zip(moves, moves[1:]))
    for move in moves:
        cube.apply(move)
    assert not cube.is_solved
    assert Counter(cube.facelets()) == dict.fromkeys(FACES, 9)
    for move in solve(cube.facelets()):
        cube.apply(move)
    assert cube.facelets() == SOLVED


def test_already_solved_needs_no_moves() -> None:
    assert solve(SOLVED) == []

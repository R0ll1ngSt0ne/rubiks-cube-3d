# Rubik’s Cube 3D

A Python desktop simulator with real 3D meshes, animated layer turns, and a solver that reads the current sticker arrangement rather than replaying your moves in reverse. The meshes are generated at runtime; no model downloads are needed.

## Run locally

Install [Python](https://www.python.org/downloads/) (3.12 recommended), then clone this repository and run the following from its directory:

```sh
python -m venv .venv
```

Activate it with `.venv\Scripts\Activate.ps1` on Windows PowerShell or `source .venv/bin/activate` on macOS/Linux. Then run:

```sh
python -m pip install .
python -m rubiks_cube
```

The solver dependency may require a C compiler and Python headers if pip cannot use a prebuilt wheel for your platform.

## Controls

| Control | Action |
| --- | --- |
| **U R F D L B**, or on-screen face buttons | Turn a face clockwise as viewed from that face |
| **Shift** + face key, or on-screen prime (`'`) buttons | Turn a face counterclockwise |
| Left-drag the cube, or use arrow keys | Orbit the camera without changing the cube |
| Scroll wheel | Zoom |
| **Scramble** / **Space** | Animate a random sequence of legal moves |
| **Auto-solve** / **Enter** | Compute and animate a solution to the current state |
| **Reset** / **Backspace** | Cancel playback and restore the solved cube and default view |

Notation: `R` is a clockwise right-face turn, `R'` is counterclockwise, and `R2` is a half turn. The status area shows the current move and the scramble or solution sequence during playback.

## Development

```sh
python -m pip install -e ".[dev]"
python -m ruff check .
python -m mypy
python -m pytest
python -m build
```

- `cube.py`: exact integer cube state and standard face notation.
- `mesh.py`: beveled cubie bodies and colored sticker meshes for Panda3D.
- `solver.py`: Kociemba two-phase solver adapter.
- `app.py`: camera, desktop controls, and animation queue.

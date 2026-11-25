"""Generate reusable Panda3D meshes for the plastic and colored tiles."""

from collections.abc import Sequence
from itertools import product

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    Vec3,
)

from rubiks_cube.cube import Vec

COLORS = {
    "U": (0.95, 0.96, 1, 1), "R": (0.90, 0.07, 0.12, 1),
    "F": (0.04, 0.71, 0.38, 1), "D": (1, 0.81, 0.08, 1),
    "L": (1, 0.34, 0.06, 1), "B": (0.08, 0.35, 0.94, 1),
}


def world(vector: Vec) -> Vec3:
    """Map right/up/front cube coordinates into right-handed Panda3D space."""
    x, y, z = vector
    return Vec3(x, -z, y)


def _mesh(name: str, faces: Sequence[list[Vec3]]) -> GeomNode:
    data = GeomVertexData(name, GeomVertexFormat.getV3n3(), Geom.UHStatic)
    vertices = GeomVertexWriter(data, "vertex")
    normals = GeomVertexWriter(data, "normal")
    triangles = GeomTriangles(Geom.UHStatic)
    start = 0
    for polygon in faces:
        normal = (polygon[1] - polygon[0]).cross(polygon[2] - polygon[0])
        center = sum(polygon, Vec3(0, 0, 0)) / len(polygon)
        if normal.dot(center) < 0:
            polygon = polygon[::-1]
            normal = -normal
        normal.normalize()
        for point in polygon:
            vertices.addData3(point)
            normals.addData3(normal)
        for i in range(1, len(polygon) - 1):
            triangles.addVertices(start, start + i, start + i + 1)
        start += len(polygon)
    geometry = Geom(data)
    geometry.addPrimitive(triangles)
    node = GeomNode(name)
    node.addGeom(geometry)
    return node


def _point(indices: tuple[int, int, int], values: tuple[float, float, float]) -> Vec3:
    xyz = [0.0, 0.0, 0.0]
    for axis, value in zip(indices, values):
        xyz[axis] = value
    return Vec3(*xyz)


def body() -> GeomNode:
    """A chamfered cube with six faces, twelve edge bevels and eight corners."""
    outer, inner = 0.48, 0.418
    ring = [(-inner, -inner), (inner, -inner), (inner, inner), (-inner, inner)]
    faces = []
    for axis in range(3):
        indices = (axis, (axis + 1) % 3, (axis + 2) % 3)
        for sign in (-1, 1):
            faces.append([_point(indices, (sign * outer, u, v)) for u, v in ring])
        for a, b in product((-1, 1), repeat=2):
            faces.append([_point(indices, point) for point in (
                (-inner, a * outer, b * inner), (inner, a * outer, b * inner),
                (inner, a * inner, b * outer), (-inner, a * inner, b * outer),
            )])
    for x, y, z in product((-1, 1), repeat=3):
        faces.append([Vec3(x * outer, y * inner, z * inner),
                      Vec3(x * inner, y * outer, z * inner),
                      Vec3(x * inner, y * inner, z * outer)])
    return _mesh("chamfered-cubie", faces)


def tile(normal: Vec) -> GeomNode:
    """Extruded octagonal sticker with a bevel around its top edge."""
    n = world(normal)
    reference = Vec3(0, 0, 1) if abs(n.z) < 0.5 else Vec3(0, 1, 0)
    u = reference.cross(n)
    v = n.cross(u)

    def outline(radius: float, corner: float, depth: float) -> list[Vec3]:
        edge = radius - corner
        return [n * depth + u * a + v * b for a, b in (
            (-edge, -radius), (edge, -radius), (radius, -edge), (radius, edge),
            (edge, radius), (-edge, radius), (-radius, edge), (-radius, -edge),
        )]

    bottom, top = outline(0.392, 0.062, 0.479), outline(0.377, 0.057, 0.514)
    sides = [[bottom[i - 1], bottom[i], top[i], top[i - 1]] for i in range(8)]
    return _mesh("beveled-tile", [top, *sides])

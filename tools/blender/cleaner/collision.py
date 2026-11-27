"""World-space checks against original Deck16 BSP solids."""
import math
from mathutils import Vector
from mathutils.bvhtree import BVHTree


class DeckCollision:
    def __init__(self, map_data, unreal_to_world):
        vertices, polygons = [], []
        for surface in map_data['polys']:
            # Portal and nonsolid surfaces render but cannot support a character.
            if surface['flags'] & (0x8 | 0x04000000 | 0x80):
                continue
            first = len(vertices)
            vertices.extend(map(unreal_to_world, surface['v']))
            polygons.append(tuple(range(first + len(surface['v']) - 1, first - 1, -1)))
        self.tree = BVHTree.FromPolygons(vertices, polygons, all_triangles=False)
        self.surfaces = [[vertices[i] for i in face] for face in polygons]

    def verify_mesh(self, vertices, faces, floor, label):
        """Check the animated surface as well as its swept body envelope."""
        body = BVHTree.FromPolygons(vertices, faces, all_triangles=True)
        for index, surface in body.overlap(self.tree):
            # Contact triangles at the original support plane are expected.
            flat_support=all(abs(v.z-floor)<.004 for v in self.surfaces[surface])
            if flat_support and min(vertices[i].z for i in faces[index]) >= floor - .004:
                continue
            points=[tuple(round(axis,3) for axis in vertices[i]) for i in faces[index]]
            raise ValueError(f'{label} intersects solid Deck16 at triangle {index}: {points}')

    def trace(self, start, end):
        start, end = Vector(start), Vector(end)
        delta = end - start
        if delta.length < 1e-6:
            return None
        point, _, _, _ = self.tree.ray_cast(start, delta.normalized(), delta.length)
        return point

    def clearance(self, point):
        _, _, _, distance = self.tree.find_nearest(Vector(point))
        return float('inf') if distance is None else distance

    def floor(self, x, y, nominal, tolerance=.17):
        point, normal, _, _ = self.tree.ray_cast(
            Vector((x, y, nominal + tolerance)), Vector((0, 0, -1)), 2*tolerance
        )
        if point is None or normal.z < .68:
            return None
        return point.z

    def verify_support(self, point, radius=.075):
        x, y, z = point
        for dx, dy in ((0, 0), (-radius, 0), (radius, 0), (0, -radius), (0, radius)):
            floor = self.floor(x + dx, y + dy, z, .13)
            if floor is None or abs(z - floor) > .035:
                raise ValueError(f'Unsupported planted foot at {tuple(round(n, 3) for n in point)}')

    def sweep(self, start, end, radius, label):
        start, end = Vector(start), Vector(end)
        steps = max(1, math.ceil((end - start).length / (radius * .55)))
        if self.trace(start, end) is not None:
            raise ValueError(f'{label} crosses solid BSP between {tuple(start)} and {tuple(end)}')
        for step in range(steps + 1):
            point = start.lerp(end, step / steps)
            if self.clearance(point) < radius:
                raise ValueError(f'{label} has less than {radius:.2f} m clearance at {tuple(point)}')

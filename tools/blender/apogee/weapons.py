"""Mount stock third-person weapons to the three animated mesh markers."""
import json
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

from paths import ASSETS

MODELS = {
    'shock': ('ASMD2hand', -90, (.09, 0, -.11)),
    'flak': ('FlakHand', 90, (.09, 0, -.12)),
    'rocket': ('EightHand', 90, (.10, 0, -.15)),
}


def create(kind, name, ut):
    model, yaw, offset = MODELS[kind]
    path = ASSETS / 'meshes' / (model + '.npz')
    with np.load(path) as mesh:
        info = json.loads(str(mesh['info']))
    textures = {i: ut.find_texture('Botpack', texture)
                for i, texture in enumerate(info['textures']) if texture}
    gun = ut.import_prop(str(path), textures, name)
    gun.data.transform(Matrix.Rotation(math.radians(yaw), 4, 'Z'))
    gun['mount_offset'] = offset
    return gun


def frame_from_triangle(points):
    anchor, endpoint, down_marker = map(Vector, points)
    forward = (endpoint - anchor).normalized()
    down = down_marker - anchor
    up = -(down - forward * down.dot(forward)).normalized()
    left = up.cross(forward).normalized()
    transform = Matrix((forward, left, forward.cross(left))).transposed().to_4x4()
    transform.translation = anchor
    return transform


def mount(gun, actor, marker):
    evaluated = actor.evaluated_get(bpy.context.evaluated_depsgraph_get())
    triangle = [evaluated.data.vertices[marker + i].co for i in range(3)]
    matrix = frame_from_triangle(triangle)
    gun.matrix_world = actor.matrix_world @ matrix @ Matrix.Translation(Vector(gun['mount_offset']))


def muzzle(gun):
    vertices = [vertex.co for vertex in gun.data.vertices]
    extent = max(vertex.x for vertex in vertices)
    front = [vertex for vertex in vertices if vertex.x > extent - .06]
    return gun.matrix_world @ (sum(front, Vector()) / len(front))

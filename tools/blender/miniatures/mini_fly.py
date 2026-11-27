r"""MINIATURES fly-through camera (Blender side): one continuous, collision-checked flight.

outside pose -> glide into the map where the way down is free -> the route (bot navigation, see mini_route.py) ->
climb out where the way up is free -> end pose. One centripetal Catmull-Rom curve through all of it, one smoothed
speed profile (no stop between the phases), a zero-phase smoothed look direction, no roll.

"Free" means the camera never crosses a surface whose front faces it. Seen from outside, the map's walls face away
(backface culled, invisible), so gliding down through a roof is fine; walkways, beams and bars face up and are not.

Several drop-in and climb-out points are tried; each finished flight is scored (every frame-to-frame step ray-checked
for crossings, frames whose view runs into a wall closer than 1.2 m, frames looking into the empty room) and the best
one is keyed. Printed as "MINI fly: ...".
"""
import json
import math
import os

import bpy
from mathutils import Vector

UP = Vector((0, 0, 1))


def crossings(sc, dg, a, b, visible_only=True):
    """surfaces crossed on the segment a->b; with visible_only, only those facing the moving camera"""
    d = b - a
    L = d.length
    if L < 1e-6:
        return []
    v = d / L
    out, p, left = [], a.copy(), L
    while left > 1e-4:
        hit, loc, nrm, *_ = sc.ray_cast(dg, p, v, distance=left)
        if not hit:
            break
        if not visible_only or nrm.dot(v) < 0:
            out.append(loc.copy())
        step = (loc - p).length + 1e-3
        p = loc + v * 1e-3
        left -= step
    return out


def centripetal(ctrl, step):
    """centripetal Catmull-Rom (alpha 0.5) through ctrl, sampled about every <step> metres: no loops, no overshoot"""
    P = [ctrl[0] + (ctrl[0] - ctrl[1])] + list(ctrl) + [ctrl[-1] + (ctrl[-1] - ctrl[-2])]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        t0 = 0.0
        t1 = t0 + max((p1 - p0).length, 1e-4) ** 0.5
        t2 = t1 + max((p2 - p1).length, 1e-4) ** 0.5
        t3 = t2 + max((p3 - p2).length, 1e-4) ** 0.5
        n = max(2, int((p2 - p1).length / step))
        for k in range(n):
            t = t1 + (t2 - t1) * k / n
            a1 = p0 * ((t1 - t) / (t1 - t0)) + p1 * ((t - t0) / (t1 - t0))
            a2 = p1 * ((t2 - t) / (t2 - t1)) + p2 * ((t - t1) / (t2 - t1))
            a3 = p2 * ((t3 - t) / (t3 - t2)) + p3 * ((t - t2) / (t3 - t2))
            b1 = a1 * ((t2 - t) / (t2 - t0)) + a2 * ((t - t0) / (t2 - t0))
            b2 = a2 * ((t3 - t) / (t3 - t1)) + a3 * ((t - t1) / (t3 - t1))
            out.append(b1 * ((t2 - t) / (t2 - t1)) + b2 * ((t - t1) / (t2 - t1)))
    out.append(ctrl[-1].copy())
    return out


def gauss_smooth(vals, r):
    if r < 1:
        return list(vals)
    w = [math.exp(-0.5 * (k / (r / 2.0)) ** 2) for k in range(-r, r + 1)]
    out = []
    n = len(vals)
    for i in range(n):
        acc, ws = None, 0.0
        for k, wk in zip(range(-r, r + 1), w):
            j = min(n - 1, max(0, i + k))
            acc = vals[j] * wk if acc is None else acc + vals[j] * wk
            ws += wk
        out.append(acc / ws)
    return out


def ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def fly_inside(S, pts, dg, dirs):
    """flymode=inside: only the stretch flyfrom..flyto (fractions of the route) at a steady speed, looking ahead;
    the film dissolves into it from the orbit shot and dips to black at its end, so no wall is ever crossed."""
    sc, cam, cd, O, ub = S['sc'], S['cam'], S['cd'], S['O'], S['ub']
    fps, diag = O['fps'], S['diag']
    n = len(pts)
    seg = pts[int(O['flyfrom'] * (n - 1)):int(O['flyto'] * (n - 1)) + 1]
    stride = max(1, int(1.0 / max(1e-3, (seg[1] - seg[0]).length)))
    ctrl = seg[::stride] + ([seg[-1]] if (seg[::stride][-1] - seg[-1]).length > 0.1 else [])
    path = centripetal(ctrl, 0.05)
    cum = [0.0]
    for a, b in zip(path, path[1:]):
        cum.append(cum[-1] + (b - a).length)
    L = cum[-1]
    v = O['flyspeed'] * ub.SCALE
    N = max(2, int(L / v * fps))

    def at(s_):
        s_ = min(max(s_, 0.0), L)
        lo_i, hi_i = 0, len(cum) - 1
        while hi_i - lo_i > 1:
            mid = (lo_i + hi_i) // 2
            if cum[mid] <= s_:
                lo_i = mid
            else:
                hi_i = mid
        k = (s_ - cum[lo_i]) / max(1e-9, cum[hi_i] - cum[lo_i])
        return path[lo_i].lerp(path[hi_i], k)

    ahead = O['ahead'] * ub.SCALE
    pos = [at(f / (N - 1) * L) for f in range(N)]
    looks = []
    for f, p in enumerate(pos):
        d = at(f / (N - 1) * L + ahead) - p
        if f == N - 1 or d.length < 1e-4:
            d = p - pos[f - 1]
        d = d.normalized()
        d = (d + Vector((0, 0, -0.08))).normalized()      # a touch of downward look: more floor, less ceiling
        looks.append(d)
    looks = [x.normalized() for x in gauss_smooth(looks, int(fps * 0.5))]
    cam.animation_data_clear()
    cd.animation_data_clear()
    cd.lens = O['flylens']
    cd.clip_start = 0.03
    cd.dof.aperture_fstop = O['flyfstop']
    sc.view_settings.exposure = O['flyexp']
    coll, wall = [], 0
    for f in range(N):
        p, dvec = pos[f], looks[f]
        cam.location = p
        cam.rotation_euler = dvec.to_track_quat('-Z', 'Y').to_euler()
        hit, loc, *_ = sc.ray_cast(dg, p, dvec, distance=diag)
        fd = (loc - p).length if hit else diag * 0.5
        cd.dof.focus_distance = max(0.5, fd)
        if hit and fd < 2.0:
            wall += 1
        cam.keyframe_insert('location', frame=f + 1)
        cam.keyframe_insert('rotation_euler', frame=f + 1)
        cd.dof.keyframe_insert('focus_distance', frame=f + 1)
        if f and crossings(sc, dg, pos[f - 1], p):
            coll.append(f + 1)
    sc.frame_end = N
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.18
    print(f'MINI fly: inside {O["flyfrom"]:.2f}..{O["flyto"]:.2f} of the route, {L:.0f} m, {N} frames '
          f'({N / fps:.1f} s), collisions {len(coll)} {coll[:12]}, wall closer than 2 m ahead: {wall}')
    return N


def fly(S):
    """S: dict with sc, cam, cd, mapobj, O, MAP, WORK, ub, lo, hi, size, diag, gap, center, outside(t) -> (pos, look),
    add_cut(mat, z). Keys the camera and returns the frame count."""
    sc, cam, cd, O, ub = S['sc'], S['cam'], S['cd'], S['O'], S['ub']
    size, diag = S['size'], S['diag']
    fps = O['fps']
    dg = bpy.context.evaluated_depsgraph_get()
    route = json.load(open(os.path.join(S['WORK'], S['MAP'], O['fly'])))
    off = Vector((0, 0, S['gap']))
    pts = [ub.u2b(p) + off for p in route['points']]
    if O['flymode'] != 'inside' and (O['flyfrom'] > 0 or O['flyto'] < 1):   # full flight over part of the route
        pts = pts[int(O['flyfrom'] * (len(pts) - 1)):int(O['flyto'] * (len(pts) - 1)) + 1]
    o0, l0 = S['outside'](0.0)
    o1, l1 = S['outside'](1.0)

    # 1. keep clear of walls (8 directions + up/down), corrections smoothed along the path
    clear = O['clear'] * ub.SCALE
    dirs = [Vector((math.cos(a), math.sin(a), 0)) for a in (i * math.pi / 4 for i in range(8))] + [UP, -UP]
    for _ in range(3):
        push = []
        for p in pts:
            d = Vector()
            for v in dirs:
                hit, loc, *_ = sc.ray_cast(dg, p, v, distance=clear)
                if hit:
                    d -= v * (clear - (loc - p).length)
            push.append(d)
        push = gauss_smooth(push, 12)
        pts = [p + d for p, d in zip(pts, push)]
    n = len(pts)
    top = S['hi'].z + S['gap'] + 0.15 * size.z         # above everything
    if O['flymode'] == 'inside':
        return fly_inside(S, pts, dg, dirs)

    # 2. drop-in / climb-out candidates
    def glide_top(i, k, back):
        """the point above the model from which a straight glide reaches pts[i]: k = horizontal run per metre of
        height (0 = vertical), back = True for the way in (it comes from behind), False for the way out"""
        p = pts[i]
        h = top - p.z
        if not back:                                      # the way out rises back over the model, never off its edge
            c = S['center'] + off - p
            c = Vector((c.x, c.y, 0))
            c = c.normalized() if c.length > 1e-3 else Vector((1, 0, 0))
            return p + UP * h + c * k * h
        j = min(n - 1, i + 25)
        d = pts[j] - p
        d = Vector((d.x, d.y, 0))
        d = d.normalized() if d.length > 1e-3 else Vector((1, 0, 0))
        return p + UP * h - d * k * h

    def column_clear(i, going_down, k):
        p, g = pts[i], glide_top(i, k, going_down)
        a, b = (g, p) if going_down else (p, g)
        return not crossings(sc, dg, a, b)

    def room_ahead(i, dist=7.0):                         # the drop must not end facing a wall
        j = min(n - 1, i + 25)
        d = pts[j] - pts[i]
        if d.length < 1e-3:
            return False
        d = Vector((d.x, d.y, 0)).normalized()
        return not sc.ray_cast(dg, pts[i] + UP * 0.5, d, distance=dist)[0]

    def candidates(going_down):
        out = []
        rng = range(0, int(n * 0.45), 4) if going_down else range(n - 1, int(n * 0.55), -4)
        for k in (1.3, 0.85, 0.5, 0.0):
            last = None
            for i in rng:
                if last is not None and abs(i - last) < 40:
                    continue
                if (not going_down or room_ahead(i)) and column_clear(i, going_down, k):
                    out.append((i, k))
                    last = i
                    if sum(1 for c in out if c[1] == k) >= 3:
                        break
        return out

    ins_c, outs_c = candidates(True), candidates(False)
    if O['flyexit'] == 'end':                             # fly the whole route; the near fade dissolves the roof above
        outs_c = [(n - 1, 0.0)]
    if not ins_c:
        print('MINI fly: no free way down in the first 45 % of the route; starting at its first point')
        ins_c = [(0, 0.0)]
    roof_exit = not outs_c
    if roof_exit:
        print('MINI fly: no free way up near the end; the cut follows the camera on the way out')
        outs_c = [(n - 1, 0.0)]

    # 3. build one complete flight for a pair of candidates
    def build(i0, k_in, j0, k_out):
        inner = pts[i0:j0 + 1]
        s0, s1 = inner[0], inner[-1]
        h_turn = min(4.0, max(1.5, (top - s0.z) * 0.25))    # radius of the turn from falling to flying (m)
        stride = max(1, int(1.2 / max(1e-3, (inner[1] - inner[0]).length if len(inner) > 1 else 1)))
        route_ctrl = inner[::stride]
        if (route_ctrl[-1] - s1).length > 0.1:
            route_ctrl.append(s1)
        d0 = (inner[min(len(inner) - 1, 12)] - s0).normalized()
        d1 = (s1 - inner[max(0, len(inner) - 13)]).normalized()
        g0, g1 = glide_top(i0, k_in, True), glide_top(j0, k_out, False)
        ctrl = [o0, g0, g0.lerp(s0, 0.6), s0 + UP * h_turn * 0.5 - d0 * h_turn * 0.8] + route_ctrl[1:-1] + \
               [s1, s1 + UP * h_turn * 0.5 + d1 * h_turn * 0.8, g1.lerp(s1, 0.6), g1, o1]
        ctrl = [ctrl[0]] + [c for a, c in zip(ctrl, ctrl[1:]) if (c - a).length > 0.05]
        path = centripetal(ctrl, 0.08)
        cum = [0.0]
        for a, b in zip(path, path[1:]):
            cum.append(cum[-1] + (b - a).length)
        L = cum[-1]
        k0 = min(range(len(path)), key=lambda i: (path[i] - s0).length)
        k1 = min(range(k0, len(path)), key=lambda i: (path[i] - s1).length)
        low = max(0.5, top - min(s0.z, s1.z) - h_turn)
        u = [1.0 if k0 <= i <= k1 else ease((top - p.z) / low) for i, p in enumerate(path)]
        u = gauss_smooth(u, 60)

        # speed: fast in the air, flyspeed inside, smoothed; start from rest, settle at the end
        v_in = O['flyspeed'] * ub.SCALE
        v_out = max(v_in * 3, (cum[k0] + (L - cum[k1])) / (O['dive'] + O['climb']))
        vdes = gauss_smooth([v_in * a + v_out * (1 - a) for a in u], 150)

        def idx(s_):
            i = min(len(cum) - 1, max(0, int(s_ / max(1e-6, L) * (len(cum) - 1))))
            while i + 1 < len(cum) and cum[i + 1] < s_:
                i += 1
            while i > 0 and cum[i] > s_:
                i -= 1
            return i

        def at(s_):
            i = idx(s_)
            j = min(len(path) - 1, i + 1)
            seg = cum[j] - cum[i]
            k = (s_ - cum[i]) / seg if seg > 0 else 0
            return path[i].lerp(path[j], max(0.0, min(1.0, k))), i

        frames_s, s, t, dt = [], 0.0, 0.0, 1.0 / fps
        while s < L and len(frames_s) < 60 * fps:
            v = vdes[idx(s)] * max(0.08, ease(t / 1.0))
            v = min(v, max(0.02, math.sqrt(2 * (L - s) * v_out / 1.4)))   # brake towards the end pose
            frames_s.append(s)
            s += v * dt
            t += dt
        frames_s.append(L)
        N = len(frames_s)
        pos, ui = [], []
        for s_ in frames_s:
            p, i = at(s_)
            pos.append(p)
            ui.append(u[i])

        # look: towards the model while outside, along the path inside; zero-phase smoothed, never up
        f_exit = next((f for f, s_ in enumerate(frames_s) if s_ >= cum[k1]), N - 1)
        looks = []
        for f, (s_, p) in enumerate(zip(frames_s, pos)):
            ahead, _ = at(min(L, s_ + max(O['ahead'] * ub.SCALE, vdes[idx(s_)] * 0.8)))
            tang = ahead - p
            tang = tang.normalized() if tang.length > 1e-4 else Vector((1, 0, 0))
            tgt = l0.lerp(l1, f / max(1, N - 1))
            to_c = (tgt - p).normalized() if (tgt - p).length > 1e-4 else tang
            # above the model there is only the dark room: a rising path is watched forward-and-down, and every turn
            # between "along the path" and "at the model" passes through "down", never sideways through the room
            if tang.z > -0.25:
                tang = (Vector((tang.x, tang.y, 0)).normalized() * 0.97 + Vector((0, 0, -0.25))).normalized()
            w = ease(ui[f] * 3.0)
            if f >= f_exit:                               # leaving: turn back to the model within 1.2 s
                w *= 1 - ease((f - f_exit) / (fps * 1.2))
            dvec = to_c.lerp(tang, w) + Vector((0, 0, -0.9)) * math.sin(math.pi * w)
            if dvec.length < 1e-4:
                dvec = tang.copy()
            dvec.normalize()
            if dvec.z < -0.93:                            # avoid the gimbal flip when looking straight down
                dvec.z = -0.93
                dvec.normalize()
            looks.append(dvec)
        looks = [v.normalized() for v in gauss_smooth(looks, int(fps * 0.35))]

        # score
        coll = []
        for f in range(N - 1):
            if f >= f_exit and roof_exit:
                continue                                  # the cut hides everything above on the way out
            if crossings(sc, dg, pos[f], pos[f + 1]):
                coll.append(f + 1)
        wall = void = 0
        for f in range(N):
            if ui[f] < 0.25:
                continue
            hit, loc, _n, _i, obj, *_ = sc.ray_cast(dg, pos[f], looks[f], distance=diag)
            if not hit or obj is None or obj.name != S['mapobj'].name:
                void += 1                                 # looking past the model: base, table or the dark room
            elif (loc - pos[f]).length < O['wallnear']:
                wall += 1
        veil = 0                                          # frames where something near the camera is fading out
        if O['nearfade'] > 0:
            for f in range(N):
                if ui[f] > 0.05 and any(sc.ray_cast(dg, pos[f], v, distance=O['nearfade'])[0]
                                        for v in dirs + [looks[f]]):
                    veil += 1
        score = len(coll) * (8 if O['nearfade'] > 0 else 100) + wall + 2 * void + veil
        return dict(score=score, coll=coll, wall=wall, void=void, veil=veil, N=N, L=L, pos=pos, ui=ui, looks=looks,
                    f_exit=f_exit, i0=i0, k_in=k_in, j0=j0, k_out=k_out, l0=l0, l1=l1)

    best = None
    for c_in in ins_c[:12]:                               # entry first (with the first exit), then the exit
        r = build(c_in[0], c_in[1], outs_c[0][0], outs_c[0][1])
        print(f'MINI fly: try in {c_in} -> score {r["score"]} (collisions {len(r["coll"])}, wall {r["wall"]}, '
              f'void {r["void"]}, veil {r["veil"]})')
        if best is None or r['score'] < best['score']:
            best = r
    for c_out in outs_c[1:12]:
        r = build(best['i0'], best['k_in'], c_out[0], c_out[1])
        print(f'MINI fly: try out {c_out} -> score {r["score"]} (collisions {len(r["coll"])}, wall {r["wall"]}, '
              f'void {r["void"]}, veil {r["veil"]})')
        if r['score'] < best['score']:
            best = r
    B = best

    # 4. keys
    N, pos, ui, looks, f_exit = B['N'], B['pos'], B['ui'], B['looks'], B['f_exit']
    cam.animation_data_clear()
    cd.animation_data_clear()
    fs_out = max(O['fstop'] / diag, 0.0011)
    roof_nodes = []
    if (roof_exit and O['nearfade'] <= 0) or O['roofcut']:     # with the near fade, roofs dissolve by themselves
        for m in S['mapobj'].data.materials:
            if not m.node_tree.nodes.get('CutZ'):
                S['add_cut'](m, 1e6)
            roof_nodes.append(m.node_tree.nodes['CutZ'])
    for f in range(N):
        fr = f + 1
        p, dvec, ins = pos[f], looks[f], ui[f]
        cam.location = p
        cam.rotation_euler = dvec.to_track_quat('-Z', 'Y').to_euler()
        cd.lens = O['lens'] + (O['flylens'] - O['lens']) * ins
        hit, loc, *_ = sc.ray_cast(dg, p, dvec, distance=diag)
        fd_in = (loc - p).length if hit else diag * 0.5
        tgt = l0.lerp(l1, f / max(1, N - 1))
        fd_out = (tgt - p).dot(dvec)                      # outside: the model, as in the orbit shots
        cd.dof.focus_distance = max(0.5, fd_in * ins + max(0.5, fd_out) * (1 - ins))
        cd.dof.aperture_fstop = fs_out + (O['flyfstop'] - fs_out) * ins
        cd.clip_start = diag * 0.002 * (1 - ins) + 0.03 * ins
        sc.view_settings.exposure = O['exp'] + (O['flyexp'] - O['exp']) * ins
        sc.view_settings.keyframe_insert('exposure', frame=fr)
        cam.keyframe_insert('location', frame=fr)
        cam.keyframe_insert('rotation_euler', frame=fr)
        for prop in ('lens', 'clip_start'):
            cd.keyframe_insert(prop, frame=fr)
        cd.dof.keyframe_insert('focus_distance', frame=fr)
        cd.dof.keyframe_insert('aperture_fstop', frame=fr)
        if roof_nodes:                                    # on the way out nothing above the camera is drawn
            h = -0.5 if f >= f_exit else -0.5 + size.z * 2 * ease((f_exit - f) / fps)
            for nd_ in roof_nodes:
                nd_.inputs[1].default_value = p.z + h
                nd_.inputs[1].keyframe_insert('default_value', frame=fr)
    sc.frame_end = N
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.18
    print(f'MINI fly: chosen in {B["i0"]}/{n} (run {B["k_in"]}), out {B["j0"]}/{n} (run {B["k_out"]}); '
          f'path {B["L"]:.0f} m, {N} frames ({N / fps:.1f} s), collisions {len(B["coll"])} {B["coll"][:12]}, '
          f'wall-in-face {B["wall"]}, empty-room {B["void"]}, fading {B["veil"]}')
    return N

"""Generate the DemoDirector bullet-time assets (Unreal 1 "James" vertex mesh format + 8-bit BMP textures).

  python make_bullet_mesh.py C:\\Games\\UnrealTournament\\DemoDirector

Writes Models\\ddbullet_{a,d}.3d (rifle bullet, length along +X), Models\\ddring_{a,d}.3d (a quad in the YZ plane for
the air ripple) and Textures\\ddbullet.bmp / ddshine.bmp / ddring.bmp / ddwake.bmp. They are imported by the #exec lines
in DDBullet.uc / DDRing.uc.

Format: _d.3d = 48 byte header (uint16 polys, uint16 verts, rest 0) + 16 bytes per triangle
(uint16 v[3], uint8 type, uint8 color, uint8 uv[3][2], uint8 texnum, uint8 flags);
_a.3d = uint16 frames, uint16 framesize (verts*4) + one packed uint32 per vertex: x*8 (11 bit), y*8 (11 bit), z*4 (10 bit).
Coordinates must stay within +-127. MESHMAP SCALE uses Z = 2 * X because z has half the resolution.
"""
import math
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageFilter


def write_mesh(base, verts, tris):
    """tris: (i0, i1, i2, type, (u,v)x3, texnum)"""
    with open(base + "_d.3d", "wb") as f:
        f.write(struct.pack("<4H", len(tris), len(verts), 0, 0))
        f.write(b"\0" * 40)
        for (a, b, c, typ, uv, tex) in tris:
            f.write(struct.pack("<3H2B", a, b, c, typ, 0))
            for (u, v) in uv:
                f.write(struct.pack("<2B", max(0, min(255, int(round(u)))), max(0, min(255, int(round(v))))))
            f.write(struct.pack("<2B", tex, 0))
    with open(base + "_a.3d", "wb") as f:
        f.write(struct.pack("<2H", 1, len(verts) * 4))
        for (x, y, z) in verts:
            xi = int(round(x * 8)) & 0x7FF
            yi = int(round(y * 8)) & 0x7FF
            zi = int(round(z * 4)) & 0x3FF
            f.write(struct.pack("<I", xi | (yi << 11) | (zi << 22)))


def bullet(base):
    R = 22.0
    N = 16
    prof = [(-100, 0.80), (-84, 1.0), (-34, 1.0), (-31.5, 0.92), (-25.5, 0.92), (-23, 1.0), (8, 1.0)]
    for s in (0.22, 0.42, 0.60, 0.75, 0.87, 0.95):
        prof.append((8 + 92 * s, (1 - s * s) ** 0.8))
    verts = [(-100.0, 0.0, 0.0)]
    for (x, r) in prof:
        for i in range(N):
            a = 2 * math.pi * i / N
            verts.append((x, math.cos(a) * r * R, math.sin(a) * r * R))
    tip = len(verts)
    verts.append((100.0, 0.0, 0.0))

    def vi(ring, i):
        return 1 + ring * N + (i % N)

    def uvx(x):
        return (x + 100) / 200.0 * 255

    tris = []
    for i in range(N):
        u0, u1 = i / N * 255, (i + 1) / N * 255
        # base cap (texture row 0..8 = lead base)
        tris.append((0, vi(0, i + 1), vi(0, i), 1, (((u0 + u1) / 2, 0), (u1, 4), (u0, 4)), 1))
        for r in range(len(prof) - 1):
            x0, x1 = prof[r][0], prof[r + 1][0]
            a, b, c, d = vi(r, i), vi(r, i + 1), vi(r + 1, i + 1), vi(r + 1, i)
            tris.append((a, b, c, 1, ((u0, uvx(x0)), (u1, uvx(x0)), (u1, uvx(x1))), 1))
            tris.append((a, c, d, 1, ((u0, uvx(x0)), (u1, uvx(x1)), (u0, uvx(x1))), 1))
        r = len(prof) - 1
        tris.append((vi(r, i), vi(r, i + 1), tip, 1, ((u0, uvx(prof[r][0])), (u1, uvx(prof[r][0])), ((u0 + u1) / 2, 255)), 1))
    write_mesh(base, verts, tris)
    return len(verts), len(tris)


def ring(base):
    verts = [(0, -100, -100), (0, 100, -100), (0, 100, 100), (0, -100, 100)]
    tris = [(0, 1, 2, 2, ((0, 0), (255, 0), (255, 255)), 1), (0, 2, 3, 2, ((0, 0), (255, 255), (0, 255)), 1)]
    write_mesh(base, verts, tris)


def save_p(img, path):
    img.convert("RGB").quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(path)


def tex_bullet(path):
    n = 256
    rng = np.random.default_rng(7)
    v = np.linspace(0, 1, n)[:, None]          # along the bullet (row 0 = tail)
    u = np.linspace(0, 1, n, endpoint=False)[None, :]
    copper = np.array([150, 70, 24], float)   # the game's Brightness=1.0 lifts it a lot
    img = np.ones((n, n, 3)) * copper
    shade = 0.78 + 0.34 * v                     # brighter toward the tip
    img *= shade[..., None]
    # brushed-metal streaks along the length
    streak = rng.normal(0, 1, (1, n)).repeat(n, 0)
    streak = np.array(Image.fromarray(((streak * 20) + 128).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), float) - 128
    img += streak[..., None] * 0.35
    # rifling engraving: 6 slanted grooves on the bearing surface (x -84..8 -> v 0.08..0.54)
    body = ((v > 0.085) & (v < 0.54)).astype(float)
    ph = (u * 6 + v * 1.6) % 1.0
    groove = np.exp(-((ph - 0.5) / 0.09) ** 2)
    img *= (1 - 0.42 * groove * body)[..., None]
    edge = np.exp(-((ph - 0.36) / 0.035) ** 2) * body
    img += edge[..., None] * 26
    # cannelure (x -31.5..-25.5 -> v 0.342..0.372)
    can = ((v > 0.340) & (v < 0.374)).astype(float)
    knurl = 0.55 + 0.25 * (np.sin(u * 2 * math.pi * 40) > 0)
    img = img * (1 - can[..., None]) + img * can[..., None] * knurl[..., None]
    # lead base (first rows) and boat tail shading
    base = (v < 0.03).astype(float)
    img = img * (1 - base[..., None]) + np.array([58, 56, 62]) * base[..., None]
    img *= (1 - 0.25 * np.exp(-((v - 0.06) / 0.03) ** 2))[..., None]
    save_p(Image.fromarray(img.clip(0, 255).astype(np.uint8)), path)


def tex_shine(path):
    """Environment map for the translucent shell: dark, with a bright sky band and a hot spot."""
    n = 256
    y, x = np.mgrid[0:n, 0:n] / (n - 1.0)
    band = np.exp(-((y - 0.30) / 0.10) ** 2) * (0.55 + 0.45 * np.exp(-((x - 0.45) / 0.30) ** 2))
    spot = np.exp(-(((x - 0.36) / 0.07) ** 2 + ((y - 0.27) / 0.05) ** 2))
    floor = 0.16 * np.exp(-((y - 0.80) / 0.14) ** 2)
    i = (band * 0.75 + spot * 1.0 + floor).clip(0, 1)
    img = np.stack([i * 255, i * 236, i * 196], -1)
    save_p(Image.fromarray(img.astype(np.uint8)), path)


def tex_ring(path):
    """Air ripple: one strong soft ring with fainter inner rings, on black (translucent = additive)."""
    n = 256
    y, x = (np.mgrid[0:n, 0:n] - (n - 1) / 2) / ((n - 1) / 2)
    r = np.hypot(x, y)
    a = np.arctan2(y, x)
    wob = 1 + 0.012 * np.sin(a * 7) + 0.008 * np.sin(a * 13 + 1.3)
    rr = r * wob
    i = 0.80 * np.exp(-((rr - 0.86) / 0.035) ** 2)                # sharp leading edge
    i += 0.30 * np.exp(-((rr - 0.80) / 0.085) ** 2)               # soft falloff behind it
    i += 0.14 * np.exp(-((rr - 0.60) / 0.040) ** 2)               # one faint inner ripple
    i += 0.035 * (rr < 0.86) * (rr / 0.86) ** 3                   # faint haze inside
    i *= (r < 0.985)
    i = i.clip(0, 1)
    img = np.stack([i * 205, i * 235, i * 255], -1)
    save_p(Image.fromarray(img.astype(np.uint8)), path)


def tex_wake(path):
    """Soft round puff for the vapour trail (translucent)."""
    n = 64
    y, x = (np.mgrid[0:n, 0:n] - (n - 1) / 2) / ((n - 1) / 2)
    r = np.hypot(x, y)
    i = (np.exp(-(r / 0.42) ** 2) * (r < 0.98)).clip(0, 1)
    img = np.stack([i * 200, i * 225, i * 255], -1)
    save_p(Image.fromarray(img.astype(np.uint8)), path)


if __name__ == "__main__":
    root = sys.argv[1]
    os.makedirs(os.path.join(root, "Models"), exist_ok=True)
    os.makedirs(os.path.join(root, "Textures"), exist_ok=True)
    print("bullet verts/tris:", bullet(os.path.join(root, "Models", "ddbullet")))
    ring(os.path.join(root, "Models", "ddring"))
    tex_bullet(os.path.join(root, "Textures", "ddbullet.bmp"))
    tex_shine(os.path.join(root, "Textures", "ddshine.bmp"))
    tex_ring(os.path.join(root, "Textures", "ddring.bmp"))
    tex_wake(os.path.join(root, "Textures", "ddwake.bmp"))
    print("done")

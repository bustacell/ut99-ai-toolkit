"""Shot, action, and sound timing for Apogee."""

from fractions import Fraction

FPS = 24
DURATION = 18
LAUNCH = 8.0
LAND = 12.5
ROCKET = 7.75
IMPACT = 12.75

MAPS = {
    'Morpheus': dict(json='DM-Morpheus', sky=('genfluid', 'NghSky'), sky_radius=700,
                     moon=1.65, rim=.48, world=(.024, .033, .055), light_scale=.021,
                     exposure=.18),
}


def timing(frame):
    return float(Fraction(frame - 1, FPS))


def shot(first, last, eye, end_eye, target, end_target, lens, **lighting):
    return dict(t=timing(first), unblock=False,
                keys=[[timing(first), eye, target, lens],
                      [timing(last), end_eye, end_target, lens]], **lighting)


def subject(actor, x, y, z):
    return dict(a=actor, off=[x, y, z])


def jump():
    # Roof measurements come from DM-Morpheus BSP in stage coordinates.
    points = [[0, -7.0, -1.15, 0], [4.5, -7.0, -1.15, 0],
              [5.08, -7.35, -1.15, 0], [6.25, -8.70, -1.15, 0],
              [7.47, -10.35, -1.15, 0], [LAUNCH, -12.10, -1.15, 0]]
    for frame in range(round(LAUNCH * FPS) + 1, round(LAND * FPS) + 1):
        t = frame / FPS
        u = (t - LAUNCH) / (LAND - LAUNCH)
        points.append([t, -12.10 - 20.55 * u, -1.15, 18.0 * u * (1 - u) - 2.56 * u])
    return points + [[13.05, -33.8, -1.15, -2.56], [14.1, -34.65, -1.15, -2.56],
                     [DURATION, -34.65, -1.15, -2.56]]


def light(at, look, color, energy, size):
    return dict(type='AREA', at=at, look=look, color=color, energy=energy, size=size)


CHAPTERS = {
    'morpheus-wide': dict(
        map='Morpheus', anchor=dict(uu=[500, 1400, 2160], yaw=270), duration=DURATION,
        key=215, fill=70,
        cast={
            'lauren': dict(mesh='SGirl', skin='Army', skinface='Lauren', team=0,
                           pos=[-7, -1.15], path=jump(), gun=False, weapon='shock',
                           height_from_stage=True, lock_feet=False,
                           face=[[0, 165], [4.4, 180, .45], [13.5, 35, .8]],
                           anim=[[0, 'StillLgFr', .22, True], [4.55, 'RunLg', .81, True],
                                 [7.75, 'JumpLgFr', .28, False],
                                 [8.30, 'POSE', 'JumpLgFr', .30],
                                 [10.5, 'POSE', 'JumpLgFr', .56],
                                 [12.18, 'POSE', 'JumpLgFr', .87],
                                 [12.45, 'LandLgFr', .9, False],
                                 [13.03, 'RunLg', .63, True],
                                 [13.92, 'StillLgFr', .22, True]],
                           rig=dict(head=[[0, 14, -1], [2.7, -14, 1], [4.35, 0, 0],
                                          [9, 0, 8], [12, 0, -10], [14.5, -9, 0]]),
                           blend=.25),
            'xan': dict(mesh='Boss', skin='boss', skinface='Xan', team=None,
                        pos=[-2.0, -1.1], gun=False, weapon='rocket', lock_feet=False, blend=.12,
                        path=[[0, -1.5, -1.10], [3.05, -1.5, -1.10],
                              [6.75, -4.15, -1.10], [18, -4.15, -1.10]],
                        face=[[0, 180], [6.7, 177, .32]],
                        anim=[[0, 'StillLgFr', .18, True], [3.05, 'WalkLg', .67, True],
                              [6.6, 'StillLgFr', .20, True]],
                        rig=dict(spine=[[0, 0, 0], [7.67, 0, 0], [7.83, 0, 9], [8.12, 0, 0]],
                                 head=[[0, 0, 2], [7.1, -3, -4], [12, 3, -4]])),
        },
        shots=[
            shot(1, 65, [38, 48, 30], [32, 42, 26], [-12, -8, -4], [-12, -8, -4], 31),
            shot(66, 119, subject('lauren', -.96, 2.35, 1.68), subject('lauren', -.75, 1.97, 1.65),
                 subject('lauren', -.14, 0, 1.27), subject('lauren', -.18, 0, 1.28), 54, key=135),
            shot(120, 166, subject('xan', -2.55, 2.5, .81), subject('xan', -2.16, 2.25, .91),
                 subject('xan', -.10, 0, 1.12), subject('xan', -.2, 0, 1.19), 53, key=155),
            shot(167, 186, subject('lauren', 2.35, 1.00, .70), subject('lauren', 2.50, 1.15, .92),
                 subject('lauren', -.10, 0, .98), subject('lauren', -.33, 0, 1.04), 31, key=95),
            shot(187, 195, subject('xan', -2.25, 1.65, .91), subject('xan', -2.30, 1.6, .92),
                 subject('xan', -.30, 0, 1.15), subject('xan', -.40, 0, 1.18), 44, key=160),
            shot(196, 231, [-16.5, -.1, 2.65], [-24.0, -3.9, 4.3], [-13, -1.15, 1.75], [-19.1, -1.15, 3.9], 25),
            shot(232, 272, subject('lauren', -1.75, -3.35, -.2), subject('lauren', -1.25, -3.7, -.54),
                 subject('lauren', -.24, .02, .88), subject('lauren', -.20, .04, .92), 43, key=135),
            shot(273, 306, [-26.6, -12.8, 5.8], [-26.9, -14.2, 5.1], [-24, -1, 1], [-24.9, -1, -.02], 24),
            shot(307, 318, [-18.0, 1.78, 2.8], [-18.35, 1.75, 2.68],
                 [-12.0, -1.25, 1.20], [-12, -1.25, 1.15], 30, key=45),
            shot(319, 363, subject('lauren', -2.58, 2.16, 1.15), subject('lauren', -2.8, 2.1, 1.23),
                 subject('lauren', -.01, 0, .96), subject('lauren', .12, 0, 1.17), 46, key=160),
            shot(364, 432, [42, 45, 29], [51, 55, 32], [-8, -15, -5], [-7, -16, -6], 28),
        ],
        lights=[
            light([-8, -5.2, 4.0], [-8, -1, 1], (.26, .53, 1), 430, 6),
            light([-4, 3.5, 2.6], [-6, -1, .8], (1, .21, .065), 220, 4),
            light([-20, -8, 5], [-21, -1, 2], (.29, .52, 1), 780, 9),
            light([-35, -4.1, 2], [-34, -.5, -1.5], (.24, .50, 1), 470, 5),
            light([-33, 2.0, .5], [-34, -.8, -1.0], (1, .37, .12), 110, 5),
        ],
        projectiles=[],
        blasts=[],
    ),
}

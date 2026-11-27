"""Camera and cast blocking for the new APOGEE sequences."""
import morpheus_score

FPS = 24

MAPS = {
    'Face': dict(json='CTF-Face', sky=('genfluid', 'NghSky3'), sky_center=(2700, 0, -1500),
                 sky_radius=720, moon=3.0, rim=1.0, world=(.018, .03, .057),
                 light_scale=.022, exposure=.42),
    'Lava': dict(json='CTF-LavaGiant', sky=('genfluid', 'DaySky'), sky_center=(64, 3200, 1232),
                 sky_radius=600, moon=1.55, rim=.78, world=(.035, .018, .013),
                 light_scale=.039, exposure=.34),
    'Hyper': dict(json='DM-HyperBlast', sky=('Indus4', 'STARSBG'), sky_center=(0, 0, 0),
                  sky_radius=650, moon=0, rim=0, world=(.018, .022, .037),
                  light_scale=.040, exposure=.40),
    'Liandri': dict(json='DM-Liandri', sky=('genfluid', 'NghSky3'), sky_center=(0, 0, 0),
                    sky_radius=450, moon=0, rim=0, world=(.017, .023, .032),
                    light_scale=.028, exposure=.40),
    'Phobos': dict(json='DM-Phobos', sky=('genfluid', 'NghSky3'), sky_center=(0, 0, 0),
                   sky_radius=700, moon=1.04, rim=.67, world=(.025, .031, .043),
                   light_scale=.029, exposure=.41),
}


def angle(start, end, eye0, eye1, look0, look1, lens, **settings):
    unblock = settings.pop('unblock', False)
    return dict(t=start, keys=[[start, eye0, look0, lens], [end, eye1, look1, lens]],
                unblock=unblock, **settings)


def light(at, look, color, power, size=4):
    return dict(type='AREA', at=at, look=look, color=color, energy=power, size=size)


def cast(mesh, skin, name, xy, weapon, **acting):
    return dict(mesh=mesh, skin=skin, skinface=name, pos=xy, gun=False, weapon=weapon,
                team=acting.pop('team', None), **acting)


FACE = dict(uu=[2750, 300, -1370], yaw=180)

MAPS.update(morpheus_score.MAPS)
CHAPTERS = dict(morpheus_score.CHAPTERS)
CHAPTERS['signal'] = dict(
    map='Face', anchor=FACE, duration=8, key=0, fill=0, cast={},
    shots=[
        angle(0, 4.5, [16, 153, 24], [12, 127, 19],
              [1, 1, 11], [2, 0, 11], 23),
        angle(4.5, 8, [-31, 76, 8], [-49, 67, 6],
              [-56, -1, 13], [-65, -1, 13], 24),
    ],
)
CHAPTERS['lava'] = dict(
    map='Lava', anchor=dict(actor='PlayerStart3', yaw=30), duration=8, key=0, fill=0, cast={},
    shots=[
        angle(0, 4.5, [-22, -37, 91], [-13, -32, 73],
              [2, -4, -9], [9, -6, -10], 24),
        angle(4.5, 8, [-8.5, -24, 21], [-2, -19, 16],
              [11, 6, -13], [15, 8, -12], 27),
    ],
)
CHAPTERS['overlook'] = dict(
    map='Face', anchor=FACE, duration=8, key=145, fill=35,
    cast={
        'lauren': cast('SGirl', 'Army', 'Lauren', [0, 1.9], 'shock', team=0,
                       face=[[0, 4]], anim=[[0, 'StillLgFr', .25, True]],
                       rig={'head': [[0, -17, 6], [2.4, 2, 0], [6, 0, 2]]}),
        'malcolm': cast('Soldier', 'Blkt', 'Malcom', [-2.32, -.68], 'flak', team=0,
                        face=[[0, 25], [5.4, 0, .7]],
                        path=[[0, -2.32, -.68], [4, -2.32, -.68], [8, 4.0, -.68]],
                        anim=[[0, 'StillLgFr', .24, True], [4, 'RunLg', .65, True]],
                        gait=(4, 8, 6.32, 1.54, .24)),
    },
    shots=[
        angle(0, 3.15, [2.0, 3.75, 1.65], [1.3, 3.7, 1.65],
              [.12, 1.9, 1.30], [.03, 1.88, 1.30], 44),
        angle(3.166, 5.45, [-2.2, -.19, 1.81], [-1.5, -.21, 1.87],
              [11, .04, 1.5], [12, .10, 1.5], 31, key=100),
        angle(5.458, 8, [4, -3.65, 1.9], [6.4, -4.58, 2.05],
              [1.5, .72, 1.05], [3.6, .54, 1.10], 32, key=95),
    ],
    lights=[light([-3, 3, 4], [0, 0, 1], (.28, .57, 1), 550),
            light([3, -4, 3], [0, 0, 1], (1, .32, .10), 240)],
)
CHAPTERS['hyperblast'] = dict(
    map='Hyper', anchor=dict(actor='PlayerStart12', yaw=-90), duration=22, key=140, fill=45,
    cast={
        'xan': cast('Boss', 'boss', 'Xan', [-.12, .48], 'rocket',
                    face=[[0, 1], [8.2, 5, .8], [14, 6, .9]],
                    anim=[[0, 'StillLgFr', .15, True], [13.3, 'CockGun', .42, False],
                          [15.1, 'StillLgFr', .17, True]], blend=.37,
                    rig={'head': [[0, -11, 7], [8.5, -5, 4], [13.2, 2, 0],
                                  [18, 0, -4], [22, 0, -4]]}),
        'malcolm': cast('Soldier', 'Blkt', 'Malcom', [7.1, -.24], 'flak',
                        face=[[0, 180]], team=0,
                        path=[[0, 7.1, -.24], [7.65, 7.1, -.24], [10.9, 4.8, -.24],
                              [22, 4.8, -.24]],
                        anim=[[0, 'StillLgFr', .22, True], [7.65, 'WalkLg', .53, True],
                              [10.9, 'StillLgFr', .18, True]], blend=.42,
                        hide=[[0, 7.55]], gait=(7.65, 10.9, 2.3, 1.16, .14),
                        rig={'head': [[0, 1, 3], [10, 4, -8], [13.7, 1, 1]]}),
    },
    shots=[
        angle(0, 4.15, [-21, -40, 19], [-16, -31, 13],
              [12, -6, 2.1], [12, -4, 1.4], 27, key=25),
        angle(4.166, 7.54, [2.18, -2.33, 1.54], [1.94, -1.96, 1.66],
              [-.02, .48, 1.23], [-.10, .42, 1.28], 49, key=90),
        angle(7.541, 11.42, [1.2, -1.55, 1.38], [2.00, -1.5, 1.49],
              [6.6, -.2, 1.04], [4.85, -.24, 1.17], 36, key=120),
        angle(11.458, 14.29, [3.2, 1.06, 1.48], [2.29, .91, 1.50],
              [-.13, .48, 1.32], [-.13, .43, 1.40], 56, key=96),
        angle(14.333, 16.5, [2.50, -1.65, 1.58], [2.63, -1.5, 1.67],
              [4.84, -.22, 1.38], [4.88, -.29, 1.41], 47, key=142),
        angle(16.541, 22, [2.15, -1.30, 1.69], [1.34, -.78, 1.70],
              [-.18, .52, 1.35], [-.20, .53, 1.44], 52, key=78),
    ],
    lights=[
        light([-1.1, 1.3, 2.6], [1, .3, 1], (.15, .65, 1), 300, 3),
        light([1.8, -1.9, 2.1], [0, .5, 1], (1, .19, .055), 285, 3.1),
        light([4.4, .2, 3.3], [4, 0, .2], (.31, .53, 1), 430, 3),
        light([6.6, 1.8, 2.5], [5, -.4, 1.05], (.29, .64, 1), 298, 3),
    ],
)

CHAPTERS['liandri'] = dict(
    map='Liandri', anchor=dict(actor='PlayerStart26', yaw=90), duration=6, key=110, fill=55,
    cast={
        'riker': cast('Soldier', 'Blkt', 'Riker', [0, 0], 'shock', team=1,
                      face=[[0, 1], [2.6, 8, .43]],
                      anim=[[0, 'StillLgFr', .18, True], [2.5, 'CockGun', .61, False],
                            [3.75, 'StillLgFr', .23, True]],
                      rig={'head': [[0, 14, -2], [2.5, -9, 1], [3.5, 0, 1]],
                           'spine': [[0, 0, -6], [3.5, 0, 0], [4.9, 0, 2]]}),
    },
    shots=[
        angle(0, 2.5, [.62, 3.65, .89], [1.21, 3.1, 1.20], [-.18, .06, .91], [0, 0, 1.12],
              27, key=95, unblock=True),
        angle(2.5, 6, [1.45, 1.92, 1.54], [1.33, 1.65, 1.59], [.22, .08, 1.22],
              [.30, .05, 1.31], 47, key=113),
    ],
    lights=[light([-3.6, -.8, 2.6], [0, 0, 1], (.14, .42, 1), 360, 3),
            light([2.9, 1.5, 2.0], [0, 0, 1.3], (1, .17, .045), 160, 2)],
)

CHAPTERS['phobos'] = dict(
    map='Phobos', anchor=dict(actor='PlayerStart10', yaw=180), duration=6, key=112, fill=40,
    cast={
        'anna': cast('FCommando', 'cmdo', 'Anna', [0, .18], 'shock', team=1,
                     face=[[0, -25], [3.7, -8, .75]],
                     anim=[[0, 'StillLgFr', .18, True]],
                     rig={'head': [[0, -15, -6], [3.6, 1, -2], [5.68, 13, 4]]}),
    },
    shots=[
        angle(0, 3.42, [-50, 49, 25], [-39, 41, 19], [8, 2, -5], [9, 2, -3],
              27, key=35),
        angle(3.416, 6, [2.05, -2.05, 1.48], [1.89, -1.8, 1.54],
              [.04, .18, 1.25], [-.05, .19, 1.27], 48, key=130),
    ],
    lights=[light([-1.3, 1.7, 2.9], [0, .2, 1.1], (.23, .58, 1), 330, 3),
            light([2.3, -2.1, 2.5], [0, .2, 1.16], (1, .42, .095), 185, 3)],
)

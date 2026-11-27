"""TAUNT ACADEMY - chapter specs (pure data; used by engine.py in Blender and by assemble.py).

Times are chapter render seconds. Stage frame: +x = open side (cameras), actors at the origin; yaw 0 = facing +x.
audio: [t, 'Pack/Name', gain_db, {opts}]  opts: slow (tempo+pitch factor), loop_until
subs:  [t0, t1, text, style, who]  style: say | ann | meme
freezes: [t, dur, top, bottom]  (held frame + meme caption, inserted in post)
"""

FACE_STAGE = {'uu': [5300, 438, -1990], 'yaw': 180}

MAPS = {
    'Face': dict(json='CTF-Face', sky=('genfluid', 'NghSky3'), sky_center=(2700, 0, -1500), sky_radius=700,
                 light_scale=0.035, moon=3.5, rim=1.2, world=(0.012, 0.016, 0.035), exposure=0.7),
    'Morpheus': dict(json='DM-Morpheus', sky=('genfluid', 'NghSky'), sky_center=(928, 0, 0), sky_radius=400,
                     light_scale=0.04, moon=3.0, rim=1.0, world=(0.02, 0.02, 0.04), exposure=0.6),
    'Deck16': dict(json='DM-Deck16', sky=('genfluid', 'NghSky3'), sky_center=(466, -30, -444), sky_radius=200,
                   light_scale=0.08, moon=0.0, rim=0.0, world=(0.06, 0.06, 0.07), exposure=1.0),
    'Coret': dict(json='CTF-Coret', sky=('ShaneSky', 'STARS'), sky_center=(624, 3200, 280), sky_radius=300,
                  light_scale=0.06, moon=0.5, rim=0.3, world=(0.05, 0.05, 0.06), exposure=0.9),
    'LavaGiant': dict(json='CTF-LavaGiant', sky=('shaneDAY', 'DayskyB'), sky_center=(64, -6400, 1232), sky_radius=500,
                      light_scale=0.04, moon=3.0, rim=1.2, world=(0.03, 0.025, 0.03), exposure=0.6),
    'Liandri': dict(json='DM-Liandri', sky=('genfluid', 'NghSky3'), sky_center=(224, -297, 2296), sky_radius=400,
                    light_scale=0.06, moon=0.5, rim=0.3, world=(0.05, 0.05, 0.05), exposure=0.9),
}


def P(mesh, skin, skinface, team=None, **kw):
    return dict(mesh=mesh, skin=skin, skinface=skinface, team=team, **kw)


# Recurring cast (UT99 stock characters)
MAL = ('Soldier', 'Blkt', 'Malcom')
BLAKE = ('Commando', 'cmdo', 'Blake')
LAUREN = ('SGirl', 'Army', 'Lauren')
GORN = ('Commando', 'cmdo', 'Gorn')
XAN = ('Boss', 'boss', 'Xan')


def stagger(start, step, n):
    return [start + i * step for i in range(n)]


CHAPTERS = {}

# ------------------------------------------------------------------------------------------- COLD OPEN
CHAPTERS['C0'] = dict(
    map='Face', anchor=FACE_STAGE, duration=2.6, key=650,
    cast={'mal': dict(**P(*MAL, team=0), pos=[0, 0], anim=[[0, 'Thrust', 0.35, True]], face=[[0, 'cam', 0.2]])},
    shots=[dict(t=0, keys=[[0, [1.55, 0.5, 0.35], 'a:mal:1.05', 15, 9], [2.6, [1.25, 0.35, 0.4], 'a:mal:1.1', 17, 6]])],
    freezes=[[2.5, 3.0, 'THIS IS MALCOLM.', 'HE HAS NEVER LOST A TAUNT.']],
    audio=[[0.0, 'Male2Voice/M2laugh', -2, {'slow': 0.6}]],
)

# ------------------------------------------------------------------------------------------- TITLE flyover
CHAPTERS['TITLE'] = dict(
    map='Face', anchor=FACE_STAGE, duration=5.0, key=200,
    cast={
        'mal': dict(**P(*MAL, team=0), pos=[0, 0], anim=[[0, 'Victory1', 0.8, True]], face=[[0, 0]]),
        'riker': dict(**P('Soldier', 'Blkt', 'Riker', team=0), path=[[0, 6, -4], [5, -2, -3]], anim=[[0, 'RunLg', 1.0, True]],
                      face=[[0, 180]]),
        'anna': dict(**P('FCommando', 'cmdo', 'Anna', team=1), path=[[0, 14, 5], [5, 6, 1]], anim=[[0, 'RunLg', 1.0, True]],
                     face=[[0, 190]]),
    },
    shots=[dict(t=0, unblock=False, keys=[[0, [36, 12, 6], [-24, 0, 27], 22], [5, [22, 6, 3.5], [-24, 0, 15], 22]])],
)

# ------------------------------------------------------------------------------------------- LESSON 1: THE CLASSIC
CHAPTERS['L1'] = dict(
    map='Face', anchor=FACE_STAGE, duration=10.0, key=700, card=('LESSON 1', 'THE CLASSIC'),
    cast={
        'mal': dict(**P(*MAL, team=0), path=[[0, -1, 0], [1.3, -1, 0], [4.0, 1.7, 0.1]],
                    anim=[[0, 'Breath1'], [0.45, 'StillFrRp', 1.0, False], [1.3, 'WalkLg', 0.6, True], [4.0, 'Thrust', 0.45, True],
                          [7.6, 'Breath1', 0.5, True]],
                    face=[[0, 'blake', 0.2], [7.6, 'cam', 0.8]]),
        'blake': dict(**P(*BLAKE, team=1), pos=[3.2, 0], anim=[[0, 'Breath1'], [0.75, 'Dead1', 1.0, False]],
                      face=[[0, 'mal', 0.1]]),
    },
    fx=[dict(type='beam', t=0.7, **{'from': 'a:mal:1.15', 'to': 'a:blake:1.0'}), dict(type='flash', t=0.72, at='a:blake:0.6', energy=2500)],
    shots=[
        dict(t=0, keys=[[0, {'a': 'mal', 'off': [-2.4, -0.9, 1.65]}, 'a:blake:0.9', 32], [1.3, {'a': 'mal', 'off': [-2.1, -0.8, 1.6]}, 'a:blake:0.8', 34]]),
        dict(t=1.3, keys=[[1.3, [-0.2, -3.8, 0.35], 'a:mal:1.0', 26, 4], [4.0, [2.0, -3.4, 0.4], 'a:mal:1.0', 28, 2]]),
        dict(t=4.0, shake=0.012, keys=[[4.0, {'a': 'mal', 'off': [1.05, -0.75, 0.2]}, 'a:mal:1.15', 16, -14],
                                       [7.6, {'a': 'mal', 'off': [0.95, -0.6, 0.22]}, 'a:mal:1.2', 17, -10]]),
        dict(t=7.6, keys=[[7.6, {'a': 'mal', 'off': [1.5, 0.35, 1.38]}, 'a:mal:1.32', 48], [10, {'a': 'mal', 'off': [1.05, 0.2, 1.36]}, 'a:mal:1.33', 60]]),
    ],
    letterbox=[[1.3, 7.6]],
    freezes=[[9.4, 2.4, 'CONFIDENCE: 100%', 'DIGNITY: 0%']],
    audio=[[0.66, 'Botpack/ASMD.TazerFire', -3, {}], [0.8, 'MaleSounds/(All).deathc3', -4, {}],
           [4.35, 'Male2Voice/M2yalikethat', 0, {'slow': 0.62}], [6.4, 'Male2Voice/M2laugh', -2, {'slow': 0.7}]],
    subs=[[4.35, 6.2, 'Ya like that?', 'say', 'MALCOLM']],
)

# ------------------------------------------------------------------------------------------- LESSON 2: THE STARE
CHAPTERS['L2'] = dict(
    map='Morpheus', anchor={'actor': 'PlayerStart4'}, duration=9.0, key=650, card=('LESSON 2', 'THE STARE'),
    cast={
        'lauren': dict(**P(*LAUREN, team=0), pos=[0, 0],
                       anim=[[0, 'StillFrRp', 0.8, False], [1.2, 'Breath1', 0.3, True]],
                       face=[[0, 'gorn', 0.1], [1.6, 'cam', 2.4], [8.0, 'cam', 0.35]]),
        'gorn': dict(**P(*GORN, team=1), pos=[4.2, -1.6], anim=[[0, 'Breath1'], [0.75, 'Dead3', 1.0, False]], face=[[0, 'lauren', 0.1]]),
    },
    fx=[dict(type='beam', t=0.65, **{'from': 'a:lauren:1.1', 'to': 'a:gorn:1.0'})],
    shots=[
        dict(t=0, keys=[[0, [6.5, 4.5, 2.4], [2.0, -0.8, 1.0], 24], [1.6, [6.2, 4.0, 2.2], [1.8, -0.6, 1.0], 25]]),
        dict(t=1.6, ease=False, keys=[[1.6, {'a': 'lauren', 'off': [2.0, 0.0, 1.3]}, 'a:lauren:1.3', 32],
                                      [5.0, {'a': 'lauren', 'off': [5.2, 0.0, 1.3]}, 'a:lauren:1.3', 85]]),
        dict(t=5.0, keys=[[5.0, {'a': 'lauren', 'off': [1.0, 0.0, 1.5]}, 'a:lauren:1.5', 70],
                          [8.0, {'a': 'lauren', 'off': [0.8, 0.0, 1.5]}, 'a:lauren:1.5', 76]]),
        dict(t=8.0, keys=[[8.0, [9, 7, 6.5], 'a:lauren:1.0', 30], [9.0, [9.5, 7.5, 7], 'a:lauren:1.0', 30]]),
    ],
    audio=[[0.6, 'Botpack/ASMD.TazerFire', -3, {}], [0.8, 'MaleSounds/(All).deathc4', -4, {}],
           [3.4, 'AmbOutside/Looping.cricket1', -6, {'loop_until': 8.0}], [8.15, 'Announcer/(All).dominating', 0, {}]],
    subs=[[8.15, 9.0, 'DOMINATING', 'ann', '']],
    music_cut=1.4,
)

# ------------------------------------------------------------------------------------------- LESSON 3: THE WELCOME COMMITTEE
COMMITTEE = {'riker': ([1.7, 1.6], ('Soldier', 'Blkt', 'Riker'), 0), 'anna': ([2.1, -0.5], ('FCommando', 'cmdo', 'Anna'), 0),
             'whitman': ([1.0, -2.0], ('Commando', 'cmdo', 'Whitman'), 0), 'rylisa': ([0.9, 2.5], ('SGirl', 'Army', 'Rylisa'), 0)}
_l3cast = {'othello': dict(**P('Soldier', 'Blkt', 'Othello', team=1), pos=[0, 0], hide=[[0, 1.0]],
                           anim=[[0, 'Breath1'], [1.0, 'Look', 1.0, False], [3.6, 'Breath1', 0.6, True], [8.6, 'Dead2', 1.0, False]],
                           face=[[0, 0, 0.1]])}
for i, (cid, (pos, look, team)) in enumerate(COMMITTEE.items()):
    w0 = 3.6 + i * 0.15
    anim = [[0, 'Breath1'], [w0, 'Wave', 0.85, True], [6.6, 'Breath1']]
    if cid == 'riker':
        anim += [[8.35, 'StillFrRp', 1.0, False], [8.9, 'Victory1', 1.0, False]]
    else:
        anim += [[8.9, 'Victory1', 1.0, False]]
    _l3cast[cid] = dict(**P(*look, team=team), pos=pos, anim=anim, face=[[0, 'othello', 0.1]])
CHAPTERS['L3'] = dict(
    map='Deck16', anchor={'actor': 'PlayerStart6'}, duration=10.0, key=900, fill=250, card=('LESSON 3', 'THE WELCOME COMMITTEE'),
    lights=[dict(type='AREA', at=[3, 0, 4], look=[0.8, 0, 0], energy=900, size=5, color=(0.9, 0.95, 1.0))],
    cast=_l3cast,
    fx=[dict(type='respawn', t=1.0, at=[0, 0, 0], energy=3000, life=0.45, radius=0.55, alpha=0.12),
        dict(type='beam', t=8.55, **{'from': 'a:riker:1.15', 'to': 'a:othello:1.0'})],
    shots=[
        dict(t=0, keys=[[0, [6, 4.5, 4.2], [0.6, 0, 0.8], 22], [1.0, [5.6, 4.2, 4.0], [0.6, 0, 0.8], 22]]),
        dict(t=1.0, keys=[[1.0, {'a': 'othello', 'off': [-1.7, 0.5, 1.75]}, [2.0, 0, 1.0], 26],
                          [3.6, {'a': 'othello', 'off': [-1.5, 0.4, 1.7]}, [2.0, 0, 1.05], 28]]),
        dict(t=3.6, keys=[[3.6, {'a': 'othello', 'off': [-1.3, -0.9, 1.5]}, [1.6, 0, 1.2], 26], [6.6, {'a': 'othello', 'off': [-0.9, -0.7, 1.5]}, [1.6, 0, 1.2], 30]]),
        dict(t=6.6, keys=[[6.6, {'a': 'othello', 'off': [1.05, 0.1, 1.36]}, 'a:othello:1.36', 55], [8.35, {'a': 'othello', 'off': [0.9, 0.1, 1.36]}, 'a:othello:1.36', 60]]),
        dict(t=8.35, keys=[[8.35, [5.5, -4.2, 2.6], [0.6, 0, 0.8], 24], [10, [5.8, -4.5, 2.8], [0.6, 0, 0.8], 24]]),
    ],
    audio=[[0.95, 'Botpack/General.Resp2A', -2, {}], [3.75, 'Male2Voice/M2seeya', 0, {}], [4.25, 'Female1Voice/F1sucker', 0, {}],
           [4.75, 'Male1Voice/M1loser', 0, {}], [5.25, 'Female2Voice/F2yousuck', 0, {}], [6.9, 'Announcer/(All).lastplace', 0, {}],
           [8.5, 'Botpack/ASMD.TazerFire', -3, {}], [8.65, 'MaleSounds/(All).deathc1', -4, {}], [9.0, 'Male2Voice/M2laugh', -4, {}]],
    subs=[[3.75, 4.3, 'See ya!', 'say', 'RIKER'], [4.25, 4.8, 'Sucker!', 'say', 'ANNA'], [4.75, 5.3, 'Loser.', 'say', 'WHITMAN'],
          [5.25, 6.4, 'You suck!', 'say', 'RYLISA'], [6.9, 8.2, 'LAST PLACE', 'ann', '']],
)

# ------------------------------------------------------------------------------------------- LESSON 4: TEAMWORK
TEAM = [('mal', MAL), ('lauren', LAUREN), ('riker', ('Soldier', 'Blkt', 'Riker')), ('anna', ('FCommando', 'cmdo', 'Anna')),
        ('wraith', ('Soldier', 'Gard', 'Wraith')), ('sara', ('SGirl', 'Army', 'Sara'))]
_l4cast = {}
for i, (cid, look) in enumerate(TEAM):
    v0 = 0.3 + i * 0.25
    _l4cast[cid] = dict(**P(*look, team=0), pos=[0.6, -2.5 + i * 1.0],
                        anim=[[0, 'Breath1'], [v0, 'Victory1', 1.0, False], [v0 + 1.7, 'Breath1'], [3.0, 'Thrust', 0.7, True],
                              [6.0, 'Breath1', 0.6, True]],
                        face=[[0, 0, 0.1], [6.2, 'cam', 0.12]])
CHAPTERS['L4'] = dict(
    map='Coret', anchor={'actor': 'FlagBase0', 'shift': 0.8}, duration=8.0, key=900, fill=250, card=('LESSON 4', 'TEAMWORK'),
    cast=_l4cast,
    lights=[dict(type='AREA', at=[4, 0, 3.5], look=[0.6, 0, 1], energy=700, size=6)],
    shots=[
        dict(t=0, keys=[[0, [2.4, -3.8, 0.55], [0.6, -2.2, 1.0], 22], [3.0, [2.4, 3.8, 0.55], [0.6, 2.2, 1.0], 22]]),
        dict(t=3.0, keys=[[3.0, [3.6, -3.2, 1.9], [0.6, 0, 1.0], 18, 0], [6.0, [3.6, 3.2, 1.2], [0.6, 0, 1.0], 18, -10]]),
        dict(t=6.0, keys=[[6.0, [4.3, 0, 1.3], [0.6, 0, 1.1], 20], [8.0, [4.0, 0, 1.3], [0.6, 0, 1.1], 21]]),
    ],
    freezes=[[6.75, 2.2, 'TEAMWORK', 'MAKES THE DREAM WORK']],
    audio=[[0.1, 'Botpack/CTF.CaptureSound2', -4, {}], [3.05, 'Male2Voice/M2yeehaw', 0, {}], [3.45, 'Female2Voice/F2ohyeah', 0, {}],
           [3.85, 'Male2Voice/M2laugh', -1, {}], [4.25, 'Female1Voice/F1letsrock', 0, {}], [4.65, 'Male2Voice/M2wantsome', 0, {}],
           [5.05, 'Female2Voice/F2sweet', 0, {}]],
    subs=[[3.05, 3.45, 'Yeehaw!', 'say', 'MALCOLM'], [3.45, 3.85, 'Oh yeah!', 'say', 'LAUREN'], [4.25, 4.65, "Let's rock!", 'say', 'ANNA'],
          [4.65, 5.05, 'Want some?', 'say', 'WRAITH'], [5.05, 5.8, 'Sweet.', 'say', 'SARA']],
)

# ------------------------------------------------------------------------------------------- LESSON 5: KARMA
CHAPTERS['L5'] = dict(
    map='LavaGiant', anchor={'actor': 'PlayerStart0', 'yaw': 0}, duration=8.0, key=750, card=('LESSON 5', 'KARMA'),
    cast={
        'gorn': dict(**P(*GORN, team=1), pos=[1.0, 1.5], hide=[[5.22, 99]],
                     anim=[[0, 'StillFrRp', 0.9, False], [1.0, 'Victory1', 0.9, False], [2.5, 'Thrust', 0.85, True]],
                     face=[[0, 'boris', 0.1], [1.0, 'cam', 0.3]]),
        'boris': dict(**P('Commando', 'daco', 'Boris', team=0), pos=[4.2, 5.4], anim=[[0, 'Breath1'], [0.6, 'Dead4', 1.0, False]],
                      face=[[0, 'gorn', 0.1]]),
        'lauren': dict(**P(*LAUREN, team=0), pos=[28, 1.0], anim=[[0, 'StillFrRp', 0.4, True], [5.7, 'Wave', 0.9, True]],
                       face=[[0, 'gorn', 0.1], [5.5, 'cam', 0.3]]),
    },
    fx=[dict(type='beam', t=0.55, **{'from': 'a:gorn:1.15', 'to': 'a:boris:1.0'}),
        dict(type='beam', t=5.18, **{'from': 'a:lauren:1.15', 'to': 'a:gorn:1.0'}),
        dict(type='combo', t=5.2, at='a:gorn:1.0', energy=8000)],
    shots=[
        dict(t=0, keys=[[0, [6.0, -1.5, 1.9], [2.6, 3.5, 1.0], 24], [1.0, [5.8, -1.2, 1.8], [2.6, 3.4, 1.0], 24]]),
        dict(t=1.0, keys=[[1.0, {'a': 'gorn', 'off': [2.3, -1.6, 0.45]}, 'a:gorn:1.1', 20, 6], [5.22, {'a': 'gorn', 'off': [1.9, 1.9, 0.55]}, 'a:gorn:1.1', 22, -6]]),
        dict(t=5.22, unblock=False, keys=[[5.22, {'a': 'gorn', 'off': [-0.8, 0.3, 1.7]}, 'a:lauren:1.2', 28], [8.0, {'a': 'gorn', 'off': [-0.8, 0.3, 1.7]}, 'a:lauren:1.3', 110]]),
    ],
    letterbox=[[1.0, 5.22]],
    freezes=[[5.24, 2.4, 'LESSON 5:', 'NEVER TAUNT IN THE OPEN']],
    audio=[[0.5, 'Botpack/ASMD.TazerFire', -3, {}], [0.7, 'MaleSounds/(All).deathc51', -4, {}],
           [1.2, 'Male1Voice/M1yousuck', 0, {}], [2.7, 'Male1Voice/M1letsrock', 0, {}],
           [5.1, 'Botpack/ASMD.TazerFire', -2, {}], [5.2, 'Botpack/General.Explg02', 1, {}],
           [5.3, 'Announcer/(All).headshot', 0, {'after_freeze': True}], [6.4, 'Female1Voice/F1toasted', 0, {}]],
    subs=[[1.2, 2.2, 'You suck!', 'say', 'GORN'], [2.7, 3.6, "Let's rock!", 'say', 'GORN'],
          [5.3, 6.4, 'HEADSHOT', 'ann', ''], [5.9, 6.4, "(it wasn't)", 'say', ''], [6.4, 7.6, 'Toasted!', 'say', 'LAUREN']],
)

# ------------------------------------------------------------------------------------------- LESSON 6: THE CHAMPION
GUARDS = {'blake': ([2.5, -2.0], BLAKE, 1, [9, -9]), 'ivana': ([2.8, 1.6], ('FCommando', 'cmdo', 'Ivana'), 1, [9, 9]),
          'drake': ([1.6, 2.8], ('Soldier', 'Gard', 'Drake'), 1, [-3, 12]), 'kyla': ([1.8, -3.3], ('FCommando', 'daco', 'Kyla'), 1, [-3, -12])}
_l6cast = {'xan': dict(**P(*XAN, team=None), pos=[0, 0],
                       anim=[[0, 'Breath1', 0.15, True], [5.0, 'Wave', 1.0, False], [6.0, 'Breath1', 0.3, True]],
                       face=[[0, 'cam', 0.1]])}
for cid, (pos, look, team, flee) in GUARDS.items():
    _l6cast[cid] = dict(**P(*look, team=team), path=[[0, *pos], [5.4, *pos], [7.2, *flee]],
                        anim=[[0, 'StillFrRp', 0.3, True], [5.4, 'RunLg', 1.2, True]],
                        face=[[0, 'xan', 0.1], [5.4, flee, 0.15]])
CHAPTERS['L6'] = dict(
    map='Liandri', anchor={'actor': 'PlayerStart26'}, duration=9.0, key=800, fill=200, card=('LESSON 6', 'THE CHAMPION'),
    cast=_l6cast,
    lights=[dict(type='SPOT', at=[0.5, 0, 6], look=[0, 0, 0], energy=2500, color=(1.0, 0.85, 0.6))],
    shots=[
        dict(t=0, keys=[[0, [7.5, 0.3, 1.0], 'a:xan:1.6', 24], [2.0, [7.2, 0.3, 1.0], 'a:xan:1.6', 24]]),
        dict(t=2.0, ease=False, keys=[[2.0, [5.2, 0.2, 1.5], 'a:xan:1.62', 40], [3.0, [5.1, 0.2, 1.5], 'a:xan:1.62', 42]]),
        dict(t=3.0, ease=False, keys=[[3.0, [4.0, 0.15, 1.55], 'a:xan:1.63', 62], [4.0, [3.9, 0.15, 1.55], 'a:xan:1.63', 64]]),
        dict(t=4.0, ease=False, keys=[[4.0, [3.2, 0.1, 1.58], 'a:xan:1.64', 95], [5.0, [3.1, 0.1, 1.58], 'a:xan:1.64', 100]]),
        dict(t=5.0, keys=[[5.0, [5.0, 1.2, 1.4], 'a:xan:1.2', 30], [7.0, [5.5, 1.5, 1.6], 'a:xan:1.2', 26]]),
        dict(t=7.0, keys=[[7.0, {'a': 'xan', 'off': [1.6, 0.2, 1.62]}, 'a:xan:1.6', 45], [9.0, {'a': 'xan', 'off': [1.2, 0.15, 1.62]}, 'a:xan:1.6', 55]]),
    ],
    audio=[[2.0, 'Announcer/(All).cd3', 0, {}], [3.0, 'Announcer/(All).cd2', 0, {}], [4.0, 'Announcer/(All).cd1', 0, {}],
           [5.75, 'BossVoice/(All).Brunhuman', 0, {}], [7.4, 'BossVoice/(All).Bperfection', 0, {}],
           [8.3, 'Announcer/(All).winner', 0, {}]],
    subs=[[2.0, 2.8, '3', 'ann', ''], [3.0, 3.8, '2', 'ann', ''], [4.0, 4.8, '1', 'ann', ''], [5.75, 6.9, 'Run, human.', 'say', 'XAN'],
          [7.4, 8.3, 'Perfection.', 'say', 'XAN'], [8.3, 9.0, 'WINNER', 'ann', '']],
    music_cut=0.0,
)

# ------------------------------------------------------------------------------------------- GRADUATION
CLASS = [MAL, BLAKE, LAUREN, GORN, ('Soldier', 'Blkt', 'Riker'), ('FCommando', 'cmdo', 'Anna'), ('Commando', 'cmdo', 'Whitman'),
         ('SGirl', 'Army', 'Rylisa'), ('Soldier', 'Blkt', 'Othello'), ('Soldier', 'Gard', 'Wraith'), ('SGirl', 'Army', 'Sara'),
         ('FCommando', 'cmdo', 'Ivana'), ('Soldier', 'Gard', 'Drake'), ('FCommando', 'daco', 'Kyla'), ('Commando', 'daco', 'Boris'),
         ('FCommando', 'cmdo', 'Nikita'), ('Commando', 'daco', 'Graves'), ('FCommando', 'goth', 'Cryss'), ('Soldier', 'Gard', 'Ivan'),
         XAN]
_gcast = {}
for i, look in enumerate(CLASS):
    row, col = divmod(i, 10)
    y = -7.0 + col * 1.55 + (0.75 if row else 0)
    x = 0.0 - row * 1.8
    team = None if look == XAN else (i % 2)
    _gcast[f'g{i}'] = dict(**P(*look, team=team), pos=[x, y],
                           anim=[[0, 'Breath1', 0.7, True], [2.0, 'Thrust', 0.5, True], [6.0, 'Victory1', 0.9, False]],
                           face=[[0, 'cam', 0.3]] if i % 3 == 0 else [[0, 0, 0.1], [6.0, 'cam', 0.4]])
CHAPTERS['GRAD'] = dict(
    map='Face', anchor=FACE_STAGE, duration=8.0, key=500, card=('FINAL EXAM', 'GRADUATION'),
    cast=_gcast,
    shots=[
        dict(t=0, keys=[[0, [17, 10, 8.5], [0, 0, 1.0], 24], [2.0, [10, 1.5, 2.6], [0, 0, 1.0], 24]]),
        dict(t=2.0, ease=False, keys=[[2.0, [2.1, -8.5, 0.5], [0, -5.5, 1.1], 20, 5], [6.0, [2.1, 8.5, 0.5], [0, 5.5, 1.1], 20, -5]]),
        dict(t=6.0, keys=[[6.0, [6, 0, 1.8], [-0.8, 0, 1.0], 22], [8.0, [19, 0, 9.5], [-0.8, 0, 1.0], 24]]),
    ],
    letterbox=[[2.0, 6.0]],
    freezes=[[7.9, 2.0, 'CLASS OF 1999', 'TAUNT ACADEMY']],
    audio=[[2.1, 'Male2Voice/M2yeehaw', -2, {}], [2.5, 'Female1Voice/F1ohyeah', -2, {}], [2.9, 'Male1Voice/M1ohyeah', -2, {}],
           [3.3, 'Female2Voice/F2youlikethat', -2, {}], [3.9, 'Announcer/(All).monsterkill', 1, {}],
           [5.2, 'BossVoice/(All).Bsuperior', -1, {}], [6.1, 'Male2Voice/M2laugh', -3, {}], [6.3, 'Female1Voice/F1yeehaw', -3, {}]],
    subs=[[3.9, 5.4, 'M-M-M-MONSTER KILL', 'ann', ''], [5.2, 6.0, 'Superior.', 'say', 'XAN']],
)

# ------------------------------------------------------------------------------------------- BLOOPERS
CHAPTERS['BLOOP'] = dict(
    map='Face', anchor=FACE_STAGE, duration=5.0, key=650,
    cast={
        'mal': dict(**P(*MAL, team=0), pos=[0, 0], hide=[[2.5, 99]], anim=[[0, 'SWEEP', 0, 680, 2.4]], face=[[0, 'cam', 0.1]]),
        'blake': dict(**P(*BLAKE, team=1), path=[[0, -14, 0], [2.5, -14, 0], [5.0, -26, 0]], hide=[[0, 2.5]],
                      anim=[[0, 'WalkLg', 1.0, True]], face=[[0, 180, 0.1]]),
    },
    shots=[
        dict(t=0, keys=[[0, [3.2, 0.6, 1.3], 'a:mal:1.0', 35], [2.5, [2.8, 0.5, 1.3], 'a:mal:1.0', 38]]),
        dict(t=2.5, keys=[[2.5, [-11, 3.5, 1.6], 'a:blake:1.0', 30], [5.0, [-17, 3.5, 1.6], 'a:blake:1.0', 30]]),
    ],
    audio=[[0.3, 'Male2Voice/(All).M2imhit', -2, {}], [1.4, 'Male2Voice/(All).M2mandown', -2, {}]],
    subs=[[0.1, 2.4, 'TAKE 12 - animator went home early', 'meme', ''], [2.6, 4.9, 'TAKE 31 - collision: optional', 'meme', '']],
)

ORDER = ['C0', 'TITLE', 'L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'GRAD', 'BLOOP']

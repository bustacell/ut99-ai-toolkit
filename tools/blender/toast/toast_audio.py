"""'UT: Toast Edition' sound: cue sheet (trailer clock), music plan, mixer with voice ducking, two-pass loudnorm.
Shared by toast_animatic.py and toast_compile.py."""
import json
import os
import subprocess

import numpy as np

SR = 48000


def cues(sounds, voice):
    def snd(*p):
        return os.path.join(sounds, *p)

    def vo(n):
        return os.path.join(voice, 'T_%s.wav' % n)
    return [
        (1.2, snd('Botpack', 'enforcer.Cocking.wav'), -6, 'sfx'),
        *[(1.6 + 0.35 * k, snd('Botpack', 'ChatSound.NewBeep.wav'), -16, 'sfx') for k in range(4)],
        (3.2, snd('Botpack', 'Pickups.UTHealth.wav'), -4, 'sfx'),
        (3.25, snd('Botpack', 'Pickups.AmpFire.wav'), -12, 'sfx'),
        (5.5, vo('YaLikeToast'), 0, 'voice'),
        (7.6, snd('UnrealShare', 'Menu.Select4.wav'), -3, 'sfx'),
        (13.0, snd('Botpack', 'CTF.flagtaken.wav'), -6, 'sfx'),
        (14.2, vo('IveGotYourToast'), 0, 'voice'),
        (22.8, vo('BurnYourToast'), 0, 'voice'),
        (24.4, snd('Botpack', 'Pickups.AmpFire.wav'), -8, 'sfx'),
        (24.5, snd('Botpack', 'RocketLauncher.RocketFly1.wav'), -14, 'sfx'),
        (24.95, snd('UnrealShare', 'Gibs.Thump.wav'), -8, 'sfx'),         # slice lands on Freylis (burner T_HIT)
        (25.1, snd('UnrealShare', 'Pickups.Steam.wav'), -12, 'sfx'),
        (28.2, vo('IBurnedYerToast'), 0, 'voice'),
        (32.6, snd('Botpack', 'ChatSound.NewBeep.wav'), -10, 'sfx'),
        (33.1, snd('Botpack', 'ChatSound.NewBeep.wav'), -10, 'sfx'),
        (34.0, vo('HoldThisBurnedToast'), 0, 'voice'),
        (41.8, snd('Botpack', 'Pickups.UTHealth.wav'), -6, 'sfx'),
        (42.6, vo('RomeoGotToasted'), 0, 'voice'),
        (48.6, vo('LetsEatToast'), 0, 'voice'),
        (52.1, vo('EatSomeToast'), 0, 'voice'),
        (55.3, vo('EatYerBurnedToast'), 0, 'voice'),
        (58.0, snd('UnrealShare', 'Menu.Select4.wav'), -6, 'sfx'),        # COMING NEVER lands
    ]


# (trailer t0, t1, source offset, gain_db, fade_in, fade_out)
MUSIC = [(5.0, 68.8, 28.0, -6, 0.4, 4.5)]        # menu theme to the end, fades under the stinger + credit


def load_wav(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2)


def db(g):
    return 10 ** (g / 20)


def mix(cue_list, music_path, dur, music=MUSIC, extra_bed=None):
    """extra_bed: optional (t0, wav_path, gain_db) for real-game audio under the reveal."""
    n = int(dur * SR) + SR
    voice_bus = np.zeros((n, 2), np.float32)
    sfx_bus = np.zeros((n, 2), np.float32)
    lens = {}
    for t, f, g, kind in cue_list:
        assert os.path.exists(f), f
        x = load_wav(f)
        lens[f] = len(x) / SR
        i = int(t * SR)
        bus = voice_bus if kind == 'voice' else sfx_bus
        bus[i:i + len(x)] += (x * db(g))[:n - i]
    if extra_bed:
        t0, f, g = extra_bed
        x = load_wav(f) * db(g)
        i = int(t0 * SR)
        sfx_bus[i:i + len(x)] += x[:n - i]
    mus = np.zeros((n, 2), np.float32)
    src = load_wav(music_path)
    for t0, t1, off, g, fi, fo in music:
        L = int((t1 - t0) * SR)
        x = src[int(off * SR):int(off * SR) + L].copy() * db(g)
        env = np.ones(len(x), np.float32)
        nfi, nfo = int(fi * SR), max(1, int(fo * SR))
        env[:nfi] = np.linspace(0, 1, nfi)
        env[-nfo:] = np.linspace(1, 0, nfo)
        i = int(t0 * SR)
        mus[i:i + len(x)] += x * env[:, None]
    duck = np.ones(n, np.float32)
    for t, f, g, kind in cue_list:
        if kind == 'voice':
            duck[max(0, int((t - 0.04) * SR)):int((t + lens[f] + 0.15) * SR)] = db(-8)
    k = int(0.3 * SR)
    duck = np.convolve(duck, np.ones(k, np.float32) / k, mode='same').astype(np.float32)
    return (voice_bus + sfx_bus + mus * duck[:, None])[:int(dur * SR)], lens


def write_wav(path, x):
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-i', '-',
                          '-c:a', 'pcm_s16le', path], stdin=subprocess.PIPE)
    p.communicate(np.clip(x, -1, 1).astype(np.float32).tobytes())


def loudnorm(src, dst):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-i', src, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json',
                        '-f', 'null', '-'], capture_output=True, text=True).stderr
    js = json.loads(r[r.rindex('{'):r.rindex('}') + 1])
    af = ('loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={input_i}:measured_TP={input_tp}:measured_LRA={input_lra}:'
          'measured_thresh={input_thresh}:offset={target_offset}:linear=true').format(**js)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-af', af, '-ar', str(SR), dst], check=True)
    return js

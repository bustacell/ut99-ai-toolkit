r"""Assemble MINIATURES: exhibits + TO SCALE finale + credits, type on top, each map's own song underneath.

  python mini_film.py draft|master [--src final|test] [--keys face,deck,...]
draft:  1920x1080, crf 20 -> output\miniatures_draft.mp4 (missing frames are held, so it works mid-render)
master: 3840x2160 (Lanczos + type drawn at 4K), crf 17, -14 LUFS -> output\miniatures.mp4 + _1080p.mp4
"""
import argparse
import json
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageFilter

import mini_type as T
import prev

from paths import MUSIC, OUT, credit  # noqa: E402

WORK = prev.WORK
FPS = 24
ORDER = ['face', 'deck', 'hyperblast', 'codex', 'lavagiant', 'fractal', 'stalwart', 'morpheus', 'phobos']
END_S = 9.0                     # credits card
SR = 48000


def load_wav(name):
    with wave.open(os.path.join(MUSIC, name + '.wav')) as w:
        n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    a = a.reshape(-1, ch)
    if ch == 1:
        a = np.repeat(a, 2, axis=1)
    if sr != SR:
        idx = np.arange(0, len(a), sr / SR)
        a = a[idx.astype(int).clip(0, len(a) - 1)]
    return a


def full_offset(a, need_s):
    """First second where the music is 'full' (1-s RMS >= 70 % of the song's median) and stays for need_s."""
    win = SR
    rms = np.sqrt(np.array([np.mean(a[i:i + win] ** 2) for i in range(0, len(a) - win, win)]))
    thr = 0.7 * np.median(rms)
    for s in range(len(rms)):
        if s + need_s <= len(rms) and rms[s] >= thr:
            return float(s)
    return 0.0


def fade(n, a, b):
    return np.linspace(a, b, max(1, n), dtype=np.float32)[:, None]


def build_audio(segments, total_s, path):
    """segments: (start_s, song, len_s, offset_s or None, fade_in, fade_out, gain)"""
    mix = np.zeros((int(total_s * SR) + SR, 2), np.float32)
    cache = {}
    for st, song, ln, off, fi, fo, g in segments:
        a = cache.get(song)
        if a is None:
            a = cache[song] = load_wav(song)
        if off is None:
            off = full_offset(a, ln)
        seg = a[int(off * SR):int((off + ln) * SR)].copy()
        if len(seg) < int(ln * SR):
            seg = np.concatenate([seg, a[:int(ln * SR) - len(seg)]])
        seg[:int(fi * SR)] *= fade(int(fi * SR), 0, 1)[:len(seg[:int(fi * SR)])]
        seg[len(seg) - int(fo * SR):] *= fade(int(fo * SR), 1, 0)
        i0 = int(st * SR)
        mix[i0:i0 + len(seg)] += seg * g
        print(f'  audio {song:9s} at {st:6.1f}s from {off:5.1f}s for {ln:.1f}s')
    mix = mix[:int(total_s * SR)]
    pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2), w.setsampwidth(2), w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def frame_path(src, key, f):
    return os.path.join(WORK, src, key, f'{f:04d}.png')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['draft', 'master'])
    ap.add_argument('--src', default='final')
    ap.add_argument('--keys', default=','.join(ORDER))
    o = ap.parse_args()
    W, H, K = (3840, 2160, 2) if o.mode == 'master' else (1920, 1080, 1)
    T.set_k(K)
    plan = json.load(open(os.path.join(prev.HERE, 'plan.json'), encoding='utf-8'))
    shots = {s['key']: s for s in plan['shots']}
    keys = [k for k in o.keys.split(',') if k]

    # ---------------------------------------------------------------- edit list: (kind, key, n_frames, song)
    edit = []
    for k in keys:
        edit.append(('exhibit', k, plan['common']['frames'], shots[k]['song']))
    layout = None
    lay_p = os.path.join(WORK, 'scale_layout.json')
    if os.path.exists(os.path.join(WORK, o.src, 'scale')) and os.path.exists(lay_p):
        layout = json.load(open(lay_p))
        edit.append(('scale', 'scale', len(layout['proj']), 'Foregone'))
    edit.append(('end', 'end', int(END_S * FPS), None))
    total = sum(e[2] for e in edit)
    total_s = total / FPS

    # ---------------------------------------------------------------- audio
    segs, t = [], 0.0
    for kind, k, n, song in edit:
        ln = n / FPS
        if kind == 'exhibit':
            segs.append((max(0, t - 0.4), song, ln + 0.9, None, 0.9, 1.4, 0.9))
        elif kind == 'scale':
            segs.append((t - 0.4, song, ln + END_S + 0.4, 62.0, 1.2, 4.0, 0.9))
        t += ln
    wav = os.path.join(WORK, f'film_{o.mode}.wav')
    build_audio(segs, total_s, wav)

    # ---------------------------------------------------------------- video
    name = 'miniatures' if o.mode == 'master' else 'miniatures_draft'
    tmp = os.path.join(OUT, name + '_v.mp4')
    crf = '17' if o.mode == 'master' else '20'
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                           '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', crf,
                           '-pix_fmt', 'yuv420p', tmp], stdin=subprocess.PIPE)
    black = Image.new('RGB', (W, H), (0, 0, 0))
    last = {}
    names = {s['key']: s['plate'] for s in plan['shots']}
    no = 0
    for kind, k, n, song in edit:
        if kind == 'exhibit':
            no += 1
            s = shots[k]
            info = json.load(open(os.path.join(WORK, s['map'], 'info.json'), encoding='utf-8'))
            span = max(info['hi'][0] - info['lo'][0], info['hi'][1] - info['lo'][1]) / 50
            scale = int(round(span / 5.0) * 5)                       # the model on the plinth is 1 m wide
            mode = T.MODES[s['map'].split('-')[0]]
            nice = s['map'].split('-', 1)[1]
        print(f'{kind} {k}', flush=True)
        for f in range(1, n + 1):
            if kind == 'end':
                fr = black.copy().convert('RGBA')
                credits(fr, f / FPS)
            else:
                p = frame_path(o.src, k, f)
                if os.path.exists(p):
                    last[k] = p
                p = last.get(k)
                fr = Image.open(p).convert('RGB').resize((W, H), Image.LANCZOS) if p else black.copy()
                if o.mode == 'master':
                    fr = fr.filter(ImageFilter.UnsharpMask(radius=2, percent=40, threshold=2))
                # dip: the gallery spot switches on (0.5 s) and off (0.4 s)
                g = min(1.0, (f - 1) / 12, (n - f) / 10)
                if g < 1:
                    fr = Image.blend(black, fr, max(0.0, g))
                fr = fr.convert('RGBA')
                if kind == 'exhibit':
                    if no == 1:
                        T.title(fr, f / FPS - 0.6, t_out=5.6)
                        T.exhibit(fr, f - int(8.2 * FPS), no, nice, mode, scale, t_in=0.0, t_out=6.0)
                    else:
                        T.exhibit(fr, f, no, nice, mode, scale)
                elif kind == 'scale':
                    scale_labels(fr, f, layout, names)
            ff.stdin.write(fr.convert('RGB').tobytes())
    ff.stdin.close()
    ff.wait()

    final = os.path.join(OUT, name + '.mp4')
    af = 'loudnorm=I=-14:TP=-1.5:LRA=11' if o.mode == 'master' else 'loudnorm=I=-16:TP=-1.5'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp, '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                    '-af', af, '-ar', '48000', '-c:a', 'aac', '-b:a', '256k', '-shortest', final], check=True)
    os.remove(tmp)
    if o.mode == 'master':
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', final, '-vf', 'scale=1920:1080:flags=lanczos',
                        '-c:v', 'libx264', '-crf', '19', '-preset', 'slow', '-c:a', 'copy',
                        os.path.join(OUT, 'miniatures_1080p.mp4')], check=True)
    print('->', final, f'{total_s:.1f}s')


def scale_labels(fr, f, layout, names):
    """Finale: caption, then each model's name on a thin leader above it once it is in frame and large enough."""
    t = f / FPS
    n = len(layout['proj'])
    T.caption(fr, t - 9.0, 'TO SCALE', 'Every arena next to the one who plays it', t_out=(n / FPS) - 9.0 - 1.5)
    row = layout['proj'][f - 1]
    # the player first, while the camera is close
    px, py, _ = row['player']
    k = T.ease((t - 1.0) / 0.8) * (1 - T.ease((t - 5.0) / 0.8))
    if k > 0:
        x, y = px * 1920, py * 1080
        draw_leader(fr, x, y - 18, 120, k)
        T.put(fr, 'YOU, 1.6 M', 'reg', 17, T.IVORY, x, y - 18 - 120 - 30, track=0.3, op=k, align='center')
    for it in layout['layout']:
        x, y, z = row[it['key']]
        if z <= 0:
            continue
        x, y = x * 1920, y * 1080
        vis = 0.0 < x < 1920 and 40 < y < 1080
        if not vis:
            continue
        # fade in once the label has settled into the picture (late in the pull-back), keep to the end
        appear = T.ease((t - 6.0 - it['x0'] / layout['row'] * 8.0) / 1.0)
        if appear <= 0:
            continue
        draw_leader(fr, x, y - 10, 46, appear)
        nm = it['map'].split('-', 1)[1]
        T.put(fr, nm, 'lightit', 24, T.IVORY, x, y - 10 - 46 - 36, op=appear, align='center')
        T.put(fr, f"{max(it['w'], it['d']):.0f} M", 'reg', 13, T.BRASS, x, y - 10 - 46 - 4 - 6, track=0.3,
              op=appear, align='center')


def draw_leader(fr, x, y, length, op):
    from PIL import ImageDraw
    d = ImageDraw.Draw(fr)
    K = T.K
    d.rectangle((x * K - 0.6 * K, (y - length * op) * K, x * K + 0.6 * K, y * K), fill=T.BRASS + (int(255 * op),))


def credits(fr, t):
    lines = [('MAPS', 'Unreal Tournament (1999), Epic Games and Digital Extremes'),
             ('MUSIC', 'the original soundtrack of each map'),
             ('MODELS', 'rebuilt from the original map files'),
             ('A FILM BY', credit())]
    y = 380
    for i, (a, b) in enumerate(lines):
        k = T.ease_out((t - 0.3 - i * 0.35) / 1.0)
        T.put(fr, a, 'reg', 16, T.BRASS, 930, y + i * 74 + 8, track=0.3, op=k, align='right')
        T.put(fr, b, 'lightit', 30, T.IVORY, 990, y + i * 74 + (1 - k) * 8, op=k)
    kk = T.ease_out((t - 2.4) / 1.4)
    T.put(fr, 'KEEP UT ALIVE', 'reg', 18, T.MUTED, 960, 760, track=0.42 + (1 - kk) * 0.3, op=kk * (1 - T.ease((t - 7.6) / 1.2)),
          align='center')


if __name__ == '__main__':
    main()

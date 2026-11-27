"""TAUNT ACADEMY assembler: rendered chapter frames + graphics + UT audio -> final MP4.

python assemble.py OUT.mp4 [--draft]     (--draft: faster x264 preset, same timing)
Missing chapter frames are padded with their last frame (or black) so drafts work mid-render.
"""
import glob
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(_HERE), _HERE]
from assetpaths import MUSIC as MUS, SOUNDS as SND, WORK  # noqa: E402
from chapters import CHAPTERS  # noqa: E402

OUT = os.path.abspath(sys.argv[1])
DRAFT = '--draft' in sys.argv
ROOT = os.path.join(WORK, 'academy')
FR = os.path.join(ROOT, 'final')
GFX = os.path.join(ROOT, 'gfx')
SEG = os.path.join(ROOT, 'segments')
os.makedirs(SEG, exist_ok=True)
FPS = 24
W, H = 1920, 1080
LB = 131  # 2.35:1 letterbox bar height
X264 = ['-c:v', 'libx264', '-preset', 'veryfast' if DRAFT else 'medium', '-crf', '20' if DRAFT else '14', '-pix_fmt', 'yuv420p',
        '-r', str(FPS)]


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode:
        print(' '.join(cmd)[:2000])
        print(r.stderr[-4000:])
        raise SystemExit(f'ffmpeg failed ({r.returncode})')
    return r


def dur_of(path):
    r = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path])
    return float(r.stdout.strip())


def snd(spec):
    """'Pack/Name' -> wav path (tries the '(All).' prefix)."""
    pack, name = spec.split('/', 1)
    for cand in (name, '(All).' + name):
        p = os.path.join(SND, pack, cand + '.wav')
        if os.path.exists(p):
            return p
    raise FileNotFoundError(spec)


def ts(t):
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f'{int(h)}:{int(m):02d}:{s:05.2f}'


ASS_HEAD = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Say,Tahoma,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,60,60,{LB + 24},1
Style: Who,Tahoma,34,&H0040D0FF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,3,1,2,60,60,{LB + 24 + 72},1
Style: Ann,Arial Black,100,&H002424E8,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,4,0,1,5,0,8,60,60,190,1
Style: MemeTop,Impact,124,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,7,0,8,40,40,60,1
Style: MemeBot,Impact,124,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,7,0,2,40,40,60,1
Style: MemeSmall,Impact,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,5,0,8,40,40,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def write_ass(path, events):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(ASS_HEAD)
        for t0, t1, style, text in events:
            f.write(f'Dialogue: 0,{ts(t0)},{ts(t1)},{style},,0,0,0,,{text}\n')


# ---------------------------------------------------------------- segment builders (video only; audio events returned)

def frame_files(cid):
    fs = sorted(f for f in glob.glob(os.path.join(FR, cid, 'frames', '*.png')) if os.path.getsize(f) > 0)
    return fs


def chapter_segment(cid, name=None, t_range=None, reverse=False, extra_subs=(), extra_audio=()):
    """Frames -> clip with freezes, letterbox, subtitles. Returns (path, duration, audio_events[(t, file, gain, opts)])."""
    C = CHAPTERS[cid]
    n_total = int(round(C['duration'] * FPS))
    files = frame_files(cid)
    by_idx = {int(os.path.basename(f)[:-4]): f for f in files}
    seq = []
    last = None
    for i in range(1, n_total + 1):
        last = by_idx.get(i, last)
        seq.append(last)
    if seq[0] is None:  # nothing rendered yet: black placeholder
        black = os.path.join(SEG, 'black.png')
        if not os.path.exists(black):
            run(['ffmpeg', '-y', '-f', 'lavfi', '-i', f'color=black:s={W}x{H}', '-frames:v', '1', black])
        seq = [s or black for s in seq]
    freezes = [] if (t_range or reverse) else C.get('freezes', [])
    idx = list(range(n_total))
    if t_range:
        idx = [i for i in idx if t_range[0] <= i / FPS < t_range[1]]
    if reverse:
        idx = idx[::-1]
    # concat list with per-frame durations (freezes = long durations)
    lst = os.path.join(SEG, f'{name or cid}.txt')
    total = 0.0
    with open(lst, 'w', encoding='utf-8') as f:
        for i in idx:
            d = 1 / FPS
            t = i / FPS
            for tf, fd, *_ in freezes:
                if t <= tf < t + 1 / FPS:
                    d += fd
            f.write(f"file '{seq[i].replace(os.sep, '/')}'\nduration {d:.6f}\n")
            total += d
        f.write(f"file '{seq[idx[-1]].replace(os.sep, '/')}'\n")

    def out_t(t):
        if t_range:
            t -= t_range[0]
        return t + sum(fd for tf, fd, *_ in freezes if tf < t)

    ev = []
    for t0, t1, text, style, who in C.get('subs', []) if not (t_range or reverse) else []:
        o0, o1 = out_t(t0), out_t(t1)
        if style == 'ann':
            ev.append((o0, o1, 'Ann', r'{\fad(60,200)\t(0,180,\fscx118\fscy118)\t(180,400,\fscx100\fscy100)}' + text))
        elif style == 'meme':
            ev.append((o0, o1, 'MemeTop', text.upper()))
        else:
            ev.append((o0, o1, 'Say', r'{\fad(80,150)}' + text))
            if who:
                ev.append((o0, o1, 'Who', r'{\fad(80,150)}' + who))
    for tf, fd, top, bot in freezes:
        o0 = out_t(tf) + 1 / FPS
        ev.append((o0 + 0.15, o0 + fd, 'MemeTop', r'{\fad(0,120)}' + top))
        ev.append((o0 + 0.55, o0 + fd, 'MemeBot', r'{\fad(0,120)}' + bot))
    ev += list(extra_subs)
    ass = f'{name or cid}.ass'
    write_ass(os.path.join(SEG, ass), ev)
    vf = [f'scale={W}:{H}', 'setsar=1']
    for a, b in C.get('letterbox', []) if not (t_range or reverse) else []:
        oa, ob = out_t(a), out_t(b)
        en = f"enable='between(t,{oa:.3f},{ob:.3f})'"
        vf += [f'drawbox=x=0:y=0:w=iw:h={LB}:color=black:t=fill:{en}', f'drawbox=x=0:y=ih-{LB}:w=iw:h={LB}:color=black:t=fill:{en}']
    for tf, fd, *_ in freezes:  # white flash + slow push-in feel via brightness at freeze start
        o0 = out_t(tf) + 1 / FPS
        vf.append(f"eq=brightness=0.25:enable='between(t,{o0:.3f},{o0 + 0.08:.3f})'")
    vf.append(f'subtitles={ass}')
    out = os.path.join(SEG, f'{name or cid}.mp4')
    run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.basename(lst), '-vf', ','.join(vf), '-fps_mode', 'cfr', *X264,
         '-an', os.path.basename(out)], cwd=SEG)
    audio = []
    if not (t_range or reverse):
        for t, spec, gain, opts in C.get('audio', []):
            opts = dict(opts)
            if 'loop_until' in opts:
                opts['loop_len'] = out_t(opts['loop_until']) - out_t(t)
            audio.append((out_t(t), snd(spec), gain, opts))
        for tf, fd, *_ in freezes:
            audio.append((out_t(tf), snd('Botpack/enforcer.Cocking'), -2, {}))
    audio += list(extra_audio)
    return out, dur_of(out), audio


def still_segment(name, bg, dur, overlays=(), vf_extra='', zoom=False):
    """bg: png path or ('blur', chapter_id, frame_no). overlays: [(png, x, y, fade_in_t)]"""
    out = os.path.join(SEG, f'{name}.mp4')
    if isinstance(bg, tuple):
        files = frame_files(bg[1])
        src = files[min(bg[2], len(files) - 1)] if files else None
        inputs = ['-loop', '1', '-t', f'{dur}', '-i', src] if src else ['-f', 'lavfi', '-t', f'{dur}', '-i', f'color=0x101420:s={W}x{H}']
        base = f'[0:v]scale={W}:{H},gblur=sigma=18,eq=brightness=-0.18:saturation=0.8'
    else:
        inputs = ['-loop', '1', '-t', f'{dur}', '-i', bg]
        base = f'[0:v]scale={W}:{H}'
    if zoom:
        base += f",zoompan=z='1+0.0008*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS}"
    base += f',setsar=1,format=yuv420p{vf_extra}[b0]'
    fc = [base]
    cur = 'b0'
    for k, (png, x, y, fin) in enumerate(overlays):
        inputs += ['-loop', '1', '-t', f'{dur}', '-i', png]
        fc.append(f'[{k + 1}:v]format=rgba,fade=t=in:st={fin}:d=0.35:alpha=1[o{k}]')
        fc.append(f'[{cur}][o{k}]overlay={x}:{y}:shortest=1[b{k + 1}]')
        cur = f'b{k + 1}'
    run(['ffmpeg', '-y', *inputs, '-filter_complex', ';'.join(fc), '-map', f'[{cur}]', '-t', f'{dur}', *X264, '-an', out])
    return out, dur_of(out), []


def card_segment(cid):
    C = CHAPTERS[cid]
    out, d, _ = still_segment(f'card_{cid}', ('blur', cid, 12), 1.6, overlays=[(os.path.join(GFX, f'card_{cid}.png'), 0, 0, 0.05)])
    return out, d, [(0.0, snd('Botpack/Pickups.UTSuperHeal'), -6, {})]


def title_segment():
    out0, d0, au = chapter_segment('TITLE', name='TITLE_raw')
    out = os.path.join(SEG, 'TITLE.mp4')
    fc = ('[1:v]format=rgba,fade=t=in:st=0.9:d=0.5:alpha=1[t];[0:v][t]overlay=0:0[a];'
          "[2:v]format=rgba,fade=t=in:st=1.0:d=0.2:alpha=1,fade=t=out:st=2.6:d=0.4:alpha=1[f];"
          "[a][f]overlay=x='-1400+(t-1.0)*1500':y=150:enable='between(t,1.0,3.0)'[v]")
    run(['ffmpeg', '-y', '-i', out0, '-loop', '1', '-t', f'{d0}', '-i', os.path.join(GFX, 'title.png'), '-loop', '1', '-t', f'{d0}',
         '-i', os.path.join(GFX, 'flare.png'), '-filter_complex', fc, '-map', '[v]', '-t', f'{d0}', *X264, '-an', out])
    return out, d0, au + [(0.95, snd('Botpack/Pickups.AmpPickup'), -3, {})]


def credits_segment(dur=11.0):
    cr = os.path.join(GFX, 'credits.png')
    hgt = int(run(['ffprobe', '-v', 'error', '-show_entries', 'stream=height', '-of', 'csv=p=0', cr]).stdout.strip())
    files = frame_files('GRAD')
    src = files[-1] if files else os.path.join(SEG, 'black.png')
    speed = (hgt - H) / dur
    out = os.path.join(SEG, 'CREDITS.mp4')
    fc = (f'[0:v]scale={W}:{H},gblur=sigma=22,eq=brightness=-0.3:saturation=0.6,setsar=1,format=yuv420p[b];'
          f"[1:v]format=rgba[c];[b][c]overlay=x=0:y='-t*{speed:.2f}':shortest=1[v]")
    run(['ffmpeg', '-y', '-loop', '1', '-t', f'{dur}', '-i', src, '-loop', '1', '-t', f'{dur}', '-i', cr, '-filter_complex', fc,
         '-map', '[v]', '-t', f'{dur}', *X264, '-an', out])
    return out, dur_of(out), []


# ---------------------------------------------------------------- build sequence
print('building segments ...')
segs = []  # (name, path, dur, audio_events, transition_in, music)
segs.append(('LIANDRI',) + still_segment('LIANDRI', os.path.join(GFX, 'liandri.png'), 3.2,
                                         vf_extra=",noise=alls=18:allf=t,eq=brightness='0.02*sin(t*40)'", zoom=True)
             + ('cut',))
segs.append(('C0',) + chapter_segment('C0') + ('fadewhite',))
segs.append(('TITLE',) + title_segment() + ('fadewhite',))
for cid, tr in (('L1', 'star'), ('L2', 'circleopen'), ('L3', 'star'), ('L4', 'pixelize'), ('L5', 'star'), ('L6', 'radial'),
                ('GRAD', 'star'), ('BLOOP', 'wipeleft')):
    segs.append((f'card_{cid}',) + card_segment(cid) + (tr,))
    segs.append((cid,) + chapter_segment(cid) + ('fade',))
rev_audio = [(0.3, os.path.join(SEG, 'yalikethat_rev.wav'), 0, {})]
run(['ffmpeg', '-y', '-i', snd('Male2Voice/M2yalikethat'), '-af', 'areverse,asetrate=22050*0.8,aresample=48000', rev_audio[0][1]])
segs.append(('REWIND',) + chapter_segment('L1', name='REWIND', t_range=(4.0, 7.6), reverse=True,
                                          extra_subs=[(0.0, 3.6, 'MemeSmall', 'TAKE 47 - PLAYED BACKWARDS FOR LEGAL REASONS')],
                                          extra_audio=rev_audio) + ('cut',))
segs.append(('CREDITS',) + credits_segment() + ('fadeblack',))
segs.append(('END',) + still_segment('END', ('blur', 'GRAD', 150), 3.8, overlays=[(os.path.join(GFX, 'end.png'), 0, 0, 0.3)]) + ('fade',))

# transitions: duration per kind
TD = {'cut': 1 / FPS, 'fade': 0.25, 'fadewhite': 0.5, 'fadeblack': 0.6, 'star': 0.6, 'circleopen': 0.5, 'pixelize': 0.5,
      'radial': 0.5, 'wipeleft': 0.45}
# star wipe: inside a 5-point star growing with progress (P goes 1 -> 0 in xfade custom)
STAR = ("if(lte(hypot(X-W/2,Y-H/2),(1-P)*1.25*hypot(W/2,H/2)*"
        "(0.55+0.45*cos(5*atan2(Y-H/2,X-W/2)))),B,A)")

starts = [0.0]
for i in range(1, len(segs)):
    starts.append(starts[-1] + segs[i - 1][2] - TD[segs[i][4]])
total = starts[-1] + segs[-1][2]
print(f'{len(segs)} segments, total {total:.1f} s')

# ---------------------------------------------------------------- video: xfade chain + global overlays
inputs = []
for s in segs:
    inputs += ['-i', s[1]]
fc = []
prev = '0:v'
for i in range(1, len(segs)):
    kind = segs[i][4]
    d = TD[kind]
    off = starts[i]
    tag = f'x{i}'
    if kind == 'star':
        fc.append(f"[{prev}][{i}:v]xfade=transition=custom:expr='{STAR}':duration={d}:offset={off:.3f}[{tag}]")
    else:
        tname = 'fade' if kind == 'cut' else kind
        fc.append(f'[{prev}][{i}:v]xfade=transition={tname}:duration={d:.4f}:offset={off:.3f}[{tag}]')
    prev = tag
n_in = len(segs)
inputs += ['-loop', '1', '-i', os.path.join(GFX, 'hq.png'), '-loop', '1', '-i', os.path.join(GFX, 'watermark.png')]
title_start = starts[[s[0] for s in segs].index('TITLE')]
fc.append(f"[{prev}][{n_in}:v]overlay=W-w-40:40:enable='gte(t,{title_start + 1:.2f})':shortest=1[h]")
fc.append(f"[h][{n_in + 1}:v]overlay=W-w-30:H-h-24:enable='gte(t,{title_start + 1:.2f})':shortest=1,format=yuv420p[vout]")
video_tmp = os.path.join(SEG, 'video_all.mp4')
graph = os.path.join(SEG, 'video_graph.txt')
open(graph, 'w').write(';\n'.join(fc))
print('encoding video ...')
run(['ffmpeg', '-y', *inputs, '-/filter_complex', graph, '-map', '[vout]', '-t', f'{total:.3f}', *X264, video_tmp])

# ---------------------------------------------------------------- audio: global timeline
names = [s[0] for s in segs]


def seg_start(name):
    return starts[names.index(name)]


def seg_end(name):
    i = names.index(name)
    return starts[i] + segs[i][2]


events = []  # (global t, file, gain, opts)
for i, s in enumerate(segs):
    for t, f, g, o in s[3]:
        events.append((starts[i] + t, f, g, o))
    if s[4] in ('star', 'wipeleft', 'circleopen', 'radial', 'pixelize') and i > 0:
        events.append((starts[i], snd('Botpack/Translocator.ThrowTarget'), -8, {}))
events.append((seg_start('LIANDRI') + 2.3, snd('Announcer/prepare'), -1, {'voice': True}))
c2 = CHAPTERS['L2']
MUSIC = [  # (track, global start, global end, offset in track, gain dB)
    ('utmenu23', 0.0, seg_start('TITLE') + 0.3, 0, -9),
    ('Uttitle', seg_start('TITLE'), seg_start('L2') + c2['music_cut'], 0, -8),
    ('Godown', seg_start('card_L3'), seg_end('L3'), 12, -13),
    ('Botpck10', seg_start('card_L4'), seg_end('L4'), 24, -9),
    ('Suprfist', seg_start('card_L5'), seg_end('L5'), 36, -11),
    ('Foregone', seg_start('card_GRAD'), seg_end('GRAD'), 48, -8),
    ('utmenu23', seg_start('card_BLOOP'), total, 40, -10),
]
voice_win = []
for t, f, g, o in events:
    if 'Voice' in f or 'Announcer' in f or o.get('voice'):
        voice_win.append((t - 0.05, t + 1.3))
duck = '+'.join(f'between(t,{a:.2f},{b:.2f})' for a, b in voice_win) or '0'

ain = []
afc = []
mix = []
k = 0
for track, g0, g1, off, gain in MUSIC:
    dur = g1 - g0
    ain += ['-ss', f'{off}', '-t', f'{dur + 0.6:.3f}', '-i', os.path.join(MUS, track + '.wav')]
    dl = int(g0 * 1000)
    afc.append(f'[{k}:a]aresample=48000,aformat=channel_layouts=stereo,volume={gain}dB,afade=t=in:d=0.3,'
               f'afade=t=out:st={max(0, dur - 0.6):.3f}:d=0.6,adelay={dl}|{dl}[m{k}]')
    mix.append(f'[m{k}]')
    k += 1
afc.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0,volume='if(gt({duck},0),0.45,1)':eval=frame[music]")
sfx = []
for t, f, g, o in sorted(events):
    chain = f'[{k}:a]aresample=48000,aformat=channel_layouts=stereo'
    if o.get('slow'):
        chain += f",asetrate=48000*{o['slow']},aresample=48000"
    if 'loop_len' in o:
        ain += ['-stream_loop', '-1', '-i', f]
        chain += f",atrim=0:{o['loop_len']:.3f},afade=t=out:st={max(0, o['loop_len'] - 0.4):.3f}:d=0.4"
    else:
        ain += ['-i', f]
    dl = int(max(0, t) * 1000)
    chain += f',volume={g}dB,adelay={dl}|{dl}[s{k}]'
    afc.append(chain)
    sfx.append(f'[s{k}]')
    k += 1
afc.append(f"[music]{''.join(sfx)}amix=inputs={len(sfx) + 1}:normalize=0:duration=longest,atrim=0:{total:.3f},"
           f"alimiter=limit=0.9:level=disabled[aout]")
agraph = os.path.join(SEG, 'audio_graph.txt')
open(agraph, 'w').write(';\n'.join(afc))
audio_tmp = os.path.join(SEG, 'audio_all.wav')
print('mixing audio ...')
run(['ffmpeg', '-y', *ain, '-/filter_complex', agraph, '-map', '[aout]', '-ar', '48000', audio_tmp])

run(['ffmpeg', '-y', '-i', video_tmp, '-i', audio_tmp, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k',
     '-movflags', '+faststart', '-shortest', OUT])
print(json.dumps({'out': OUT, 'duration': dur_of(OUT), 'segments': [(n, round(starts[i], 2)) for i, n in enumerate(names)]}))

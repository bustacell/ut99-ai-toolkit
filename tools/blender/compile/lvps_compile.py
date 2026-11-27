"""LVPS compilation: title -> [card + skit] x N -> end card, xfade transitions, 2-pass loudnorm.
python lvps_compile.py --root RENDER_ROOT --assets ASSETS_DIR --out OUT.mp4 [--preview] [--skit N=path.mp4 ...]
RENDER_ROOT holds skitN/ dirs and batch1/compile/gfx (from lvps_cards.py). ASSETS_DIR = extracted UT99 assets
(sounds/Announcer, music). Writes OUT.mp4 and OUT_chapters.json (exact chapter start times).
Keep RENDER_ROOT outside the repo or under output/ (gitignored). UT content is © Epic Games."""
import argparse
import json
import math
import os
import subprocess

ap = argparse.ArgumentParser()
ap.add_argument('--root', required=True)
ap.add_argument('--assets', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--preview', action='store_true', help='640x360 quick check')
ap.add_argument('--skit', action='append', default=[], help='override N=file.mp4')
ap.add_argument('--title-bg', default=None)
ap.add_argument('--end-bg', default=None)
a = ap.parse_args()
R = os.path.abspath(a.root)
GFX = os.path.join(R, 'batch1', 'compile', 'gfx')
TMP = os.path.join(os.path.dirname(os.path.abspath(a.out)), 'compile_tmp' + ('_preview' if a.preview else ''))
os.makedirs(TMP, exist_ok=True)
W, H = (640, 360) if a.preview else (1920, 1080)
FPS, SR = 30, 48000
XD = 0.5          # transition length (s)
CARD = 1.8        # per-skit title card (s); keeps every chapter >= 10 s for YouTube
TITLE, END = 4.0, 5.0
SKITS = {
    1: ('skit1/skit1_sit_down_1080p.mp4', '"Sit down!" (Tanya)'),
    2: ('skit2/skit2_eat_that_1080p.mp4', '"Eat that!" (Blake)'),
    3: ('skit3/skit3_alpha_omega_1080p.mp4', '"I am the alpha and the omega." (Xan)'),
    4: ('skit4/skit4_safety_off_1080p.mp4', '"Try turning the safety off." (Lauren)'),
    5: ('skit5/skit5_want_some_1080p.mp4', '"Anyone else want some?" (Malcom)'),
}
for o in a.skit:
    n, p = o.split('=', 1)
    SKITS[int(n)] = (p, SKITS[int(n)][1])
# transition INTO each block (pitch): star wipe, circle open, pixelize, wipe left, radial; fade into the end card
STAR = ("if(lt(hypot(X-W/2,Y-H/2),(1-P)*hypot(W,H)*1.15*(0.42+0.58*pow(abs(cos(2.5*(atan2(Y-H/2,X-W/2)+P*2.4))),2))),B,A)")
TRANS = {1: ('custom', STAR), 2: ('circleopen', None), 3: ('pixelize', None), 4: ('wipeleft', None), 5: ('radial', None), 'end': ('fade', None)}
SND = os.path.join(a.assets, 'sounds')
MUSIC = os.path.join(a.assets, 'music', 'Foregone.wav')
PREPARE = os.path.join(SND, 'Announcer', '(All).prepare.wav')
STING = os.path.join(SND, 'Botpack', 'ASMD.TazerSelect.wav')
VENC = ['-c:v', 'libx264', '-preset', 'veryfast' if a.preview else 'slow', '-crf', '23' if a.preview else '16', '-pix_fmt', 'yuv420p', '-r', str(FPS)]
AENC = ['-c:a', 'pcm_s16le', '-ar', str(SR), '-ac', '2']
SC = f'scale={W}:{H}:flags=lanczos,setsar=1'


def run(cmd):
    print('>>', ' '.join(cmd)[:300])
    subprocess.run(cmd, check=True)


def dur(p):
    """container duration (used for the final file report)"""
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p],
                                capture_output=True, text=True, check=True).stdout.strip())


def vdur(p):
    """exact video duration = frame count / fps (xfade offsets must follow the video, not padded audio)"""
    n = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries', 'stream=nb_read_packets',
                        '-of', 'csv=p=0', p], capture_output=True, text=True, check=True).stdout.strip()
    return int(n) / FPS


def last_frame(src, out):
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-sseof', '-0.1', '-i', src, '-frames:v', '1', '-update', '1', out])


def path(p):
    return p if os.path.isabs(p) else os.path.join(R, p)


# ---------------------------------------------------------------- segments
segs = []
# title: flare sweep over black (0-1.2 s), then push-in on the skit 5 tower + chrome title; "Prepare for battle!" + Foregone
tbg = a.title_bg or os.path.join(R, 'skit5', 'final_frames', '0030.png')
t_out = os.path.join(TMP, 'title.mkv')
fx = (f"[0:v]scale=2400:1350,zoompan=z='1+0.0009*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={int(TITLE*FPS)}:s=1920x1080:fps={FPS},"
      f"gblur=sigma=4,eq=brightness=-0.16:saturation=0.8,fade=t=in:st=1.0:d=0.6[bg];"
      f"[1:v]format=rgba,fade=t=in:st=1.2:d=0.5:alpha=1[ti];"
      f"[2:v]format=rgba,scale=1400:700,colorchannelmixer=aa=0.95[fl];"
      f"[bg][ti]overlay=0:0:format=auto[b1];"
      f"[b1][fl]overlay=x='-1400+(t/1.6)*3300':y=190:enable='lt(t,1.7)',{SC},format=yuv420p[v];"
      f"[3:a]aresample={SR},aformat=channel_layouts=stereo,atrim=0:{TITLE},volume=-9dB,afade=t=in:d=0.3,afade=t=out:st={TITLE-1.2}:d=1.2[m];"
      f"[4:a]aresample={SR},aformat=channel_layouts=stereo,volume=1dB,adelay=1150|1150[p];"
      f"[m][p]amix=inputs=2:normalize=0:duration=first,atrim=0:{TITLE}[a]")
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-loop', '1', '-t', str(TITLE), '-i', tbg,
     '-loop', '1', '-t', str(TITLE), '-i', os.path.join(GFX, 'title_overlay.png'),
     '-loop', '1', '-t', str(TITLE), '-i', os.path.join(GFX, 'flare.png'),
     '-i', MUSIC, '-i', PREPARE, '-filter_complex', fx, '-map', '[v]', '-map', '[a]', '-t', str(TITLE), *VENC, *AENC, t_out])
segs.append(('title', t_out, TITLE))

blocks = []
for n in sorted(SKITS):
    src = path(SKITS[n][0])
    c_out = os.path.join(TMP, f'card_{n}.mkv')
    fx = (f"[0:v]zoompan=z='1+0.0006*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={int(CARD*FPS)}:s=1920x1080:fps={FPS},"
          f"{SC},format=yuv420p[v];"
          f"[1:a]aresample={SR},aformat=channel_layouts=stereo,volume=-6dB,apad,atrim=0:{CARD}[a]")
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-loop', '1', '-t', str(CARD), '-i', os.path.join(GFX, f'card_{n}.png'),
         '-i', STING, '-filter_complex', fx, '-map', '[v]', '-map', '[a]', '-t', str(CARD), *VENC, *AENC, c_out])
    s_out = os.path.join(TMP, f'skit_{n}.mkv')
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', src, '-vf', f'{SC},fps={FPS},format=yuv420p',
         '-af', f'aresample={SR},aformat=channel_layouts=stereo', *VENC, *AENC, s_out])
    b_out = os.path.join(TMP, f'block_{n}.mkv')
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', c_out, '-i', s_out, '-filter_complex',
         '[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]', '-map', '[v]', '-map', '[a]', *VENC, *AENC, b_out])
    blocks.append((n, b_out, vdur(b_out)))

# end card: freeze of skit 5's last frame (the party), darkened + credits, Foregone tail
ebg = a.end_bg or os.path.join(TMP, 'end_bg.png')
if not a.end_bg:
    last_frame(path(SKITS[5][0]), ebg)
e_out = os.path.join(TMP, 'end.mkv')
fx = (f"[0:v]scale=1920:1080,zoompan=z='1.04-0.0003*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={int(END*FPS)}:s=1920x1080:fps={FPS},boxblur=2[bg];"
      f"[1:v]format=rgba,fade=t=in:st=0.3:d=0.6:alpha=1[ov];[bg][ov]overlay=0:0,fade=t=out:st={END-0.8}:d=0.8,{SC},format=yuv420p[v];"
      f"[2:a]aresample={SR},aformat=channel_layouts=stereo,atrim=0:{END},volume=-12dB,afade=t=in:d=0.8,afade=t=out:st={END-1.5}:d=1.5[a]")
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-loop', '1', '-t', str(END), '-i', ebg,
     '-loop', '1', '-t', str(END), '-i', os.path.join(GFX, 'end_overlay.png'), '-ss', '30', '-i', MUSIC,
     '-filter_complex', fx, '-map', '[v]', '-map', '[a]', '-t', str(END), *VENC, *AENC, e_out])

# ---------------------------------------------------------------- xfade chain
items = [('title', t_out, TITLE)] + [(n, p, d) for n, p, d in blocks] + [('end', e_out, END)]
inputs, fv, fa = [], [], []
for _, p, _ in items:
    inputs += ['-i', p]
offset, acc = 0.0, items[0][2]
prev_v, prev_a = '0:v', '0:a'
starts = {'title': 0.0}
for i, (key, p, d) in enumerate(items[1:], start=1):
    offset = acc - XD
    tr, expr = TRANS[key]
    xf = f"transition={tr}" + (f":expr='{expr}'" if expr else '')
    fv.append(f"[{prev_v}][{i}:v]xfade={xf}:duration={XD}:offset={offset:.3f}[v{i}]")
    fa.append(f"[{prev_a}][{i}:a]acrossfade=d={XD}:c1=tri:c2=tri[a{i}]")
    prev_v, prev_a = f'v{i}', f'a{i}'
    starts[key] = offset
    acc = offset + d
total = acc
graph = ';'.join(fv + fa)
mix = os.path.join(TMP, 'joined.mkv')
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *inputs, '-filter_complex', graph, '-map', f'[{prev_v}]', '-map', f'[{prev_a}]',
     *VENC, *AENC, mix])

# ---------------------------------------------------------------- loudnorm (2 pass) -> -14 LUFS, TP -1.5 dBTP
meas = subprocess.run(['ffmpeg', '-hide_banner', '-i', mix, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'],
                      capture_output=True, text=True).stderr
j = json.loads(meas[meas.rindex('{'):meas.rindex('}') + 1])
ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
      f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample={SR}")
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', mix, '-map', '0:v', '-map', '0:a', '-c:v', 'copy', '-af', ln,
     '-c:a', 'aac', '-b:a', '256k', '-ar', str(SR), '-movflags', '+faststart', os.path.abspath(a.out)])

chap = [{'t': 0.0, 'title': 'Intro'}]
for n in sorted(SKITS):
    chap.append({'t': round(starts[n], 3), 'title': SKITS[n][1]})
chap.append({'t': round(starts['end'], 3), 'title': 'Credits'})
info = {'duration': round(dur(a.out), 3), 'computed_total': round(total, 3), 'xfade': XD, 'card': CARD,
        'blocks': {str(n): round(d, 3) for n, _, d in blocks}, 'chapters': chap, 'loudnorm_pass1': j}
with open(os.path.splitext(a.out)[0] + '_chapters.json', 'w') as f:
    json.dump(info, f, indent=1)
print(json.dumps({k: v for k, v in info.items() if k != 'loudnorm_pass1'}, indent=1))

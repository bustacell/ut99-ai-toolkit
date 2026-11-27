"""LVPS Vol. 2 episode: cold open (VHS rewind "previously on" + chrome title, Announcer "You may proceed.")
-> [title card + skit] x 5 with the pitch's transitions -> end card (Epic credit) -> black beat -> stinger.
Two-pass loudnorm to -14 LUFS / -1.5 dBTP. Based on compile/lvps_compile.py (Vol. 1); new file, Vol. 1 untouched.

    python tools/blender/compile/lvps2_compile.py --root "$LVPS_ROOT" --vol1-root "$LVPS_VOL1_ROOT" \
        --assets "$ASSETS" --out OUT.mp4 [--preview]

--root is the Vol. 2 render tree (skitN/final_v1/, stinger/final_v1/). --vol1-root holds the Vol. 1
final MP4s used in the VHS rewind. --assets is the extracted UT asset tree (sounds/, music/).
Graphics default to <outdir>/gfx (from lvps2_cards.py). Title/end backgrounds default to
skit5/final_v1/frames/0045.png and 0390.png under --root (local renders; not in the repo).
Skit 5 and the stinger prefer the *_lm.mp4 level-matched copies when present.
"""
import argparse
import json
import os
import subprocess

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--preview', action='store_true')
ap.add_argument('--root', default=os.environ.get('LVPS_ROOT'), help='Vol. 2 render root (or $LVPS_ROOT)')
ap.add_argument('--vol1-root', default=os.environ.get('LVPS_VOL1_ROOT'), help='Vol. 1 finals root for the VHS rewind (or $LVPS_VOL1_ROOT)')
ap.add_argument('--assets', default=os.environ.get('LVPS_ASSETS'), help='extracted UT assets (sounds/, music/)')
ap.add_argument('--fonts', default=os.environ.get('LVPS_FONTS', '/usr/share/fonts'))
ap.add_argument('--gfx', default=None, help='title/card/end overlays (default: <outdir>/gfx)')
ap.add_argument('--skit', action='append', default=[], help='override N=file.mp4')
ap.add_argument('--stinger', default=None)
ap.add_argument('--title-bg', default=None)
ap.add_argument('--end-bg', default=None)
a = ap.parse_args()
if not a.root:
    raise SystemExit('set --root or $LVPS_ROOT')
if not a.vol1_root:
    raise SystemExit('set --vol1-root or $LVPS_VOL1_ROOT (Vol. 1 finals for the VHS rewind)')
if not a.assets:
    raise SystemExit('set --assets or $LVPS_ASSETS')
V2 = os.path.abspath(a.root)
L1 = os.path.abspath(a.vol1_root)
ASSETS = os.path.abspath(a.assets)
OUTDIR = os.path.dirname(os.path.abspath(a.out)) or '.'
GFX = os.path.abspath(a.gfx or os.path.join(OUTDIR, 'gfx'))
TMP = os.path.join(OUTDIR, 'work', 'compile_tmp' + ('_preview' if a.preview else ''))
os.makedirs(TMP, exist_ok=True)
W, H = (640, 360) if a.preview else (1920, 1080)
FPS, SR = 30, 48000
XD = 0.5
CARD = 1.8
VHS, TITLE = 2.0, 3.0
COLD = VHS + TITLE
END, BEAT = 5.0, 0.4

def _prefer(*paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return paths[-1]

SKITS = {
    1: (_prefer(f'{V2}/skit1/final_v1/skit1_toasted_1080p.mp4'), '"Toasted!" (Cryss)'),
    2: (_prefer(f'{V2}/skit2/final_v1/skit2_lets_rock_1080p.mp4'), '"Lets Rock!" (Gorn)'),
    3: (_prefer(f'{V2}/skit3/final_v1/skit3_dirtbag_1080p.mp4'), '"Dirt bag!" (Bruce)'),
    4: (_prefer(f'{V2}/skit4/final_v1/skit4_hold_position_1080p.mp4'), '"Hold this position." (Athena)'),
    5: (_prefer(f'{V2}/skit5/final_v1/skit5_perfection_1080p_lm.mp4',
               f'{V2}/skit5/final_v1/skit5_perfection_1080p.mp4'), '"Witness my perfection." (Xan)'),
}
for o in a.skit:
    n, p = o.split('=', 1)
    n = int(n)
    SKITS[n] = (p, SKITS[n][1])
STINGER = a.stinger or _prefer(f'{V2}/stinger/final_v1/stinger_lights_out_1080p_lm.mp4',
                               f'{V2}/stinger/final_v1/stinger_lights_out_1080p.mp4')
# pitch: star wipe, zoom-in, CRT channel switch (static burst on card 3 + horizontal blur), fade from white
# (skit 3 ends on its own CRT power-off), diagonal wipe; fade into the end card
STAR = ("if(lt(hypot(X-W/2,Y-H/2),(1-P)*hypot(W,H)*1.15*(0.42+0.58*pow(abs(cos(2.5*(atan2(Y-H/2,X-W/2)+P*2.4))),2))),B,A)")
ZOOM = ("if(eq(PLANE,0),a0(floor(W/2+(X-W/2)/(1+(1-P)*1.6)),floor(H/2+(Y-H/2)/(1+(1-P)*1.6))),if(eq(PLANE,1),a1(floor(W/2+(X-W/2)/(1+(1-P)*1.6)),floor(H/2+(Y-H/2)/(1+(1-P)*1.6))),a2(floor(W/2+(X-W/2)/(1+(1-P)*1.6)),floor(H/2+(Y-H/2)/(1+(1-P)*1.6)))))*P+B*(1-P)")  # push into the outgoing shot while the card fades up (a0/a1/a2 = Y/U/V planes; no st/ld: not thread-safe)
TRANS = {1: ('custom', STAR), 2: ('custom', ZOOM), 3: ('hblur', None), 4: ('fadewhite', None), 5: ('diagtl', None), 'end': ('fade', None)}
SND = os.path.join(ASSETS, 'sounds')
RAZOR = os.path.join(ASSETS, 'music', 'Razor-ub.wav')
PROCEED = os.path.join(SND, 'Announcer', '(All).proceed.wav')
STING = os.path.join(SND, 'Botpack', 'ASMD.TazerSelect.wav')
def _find_font(*names):
    index = {}
    for root in (a.fonts, '/usr/share/fonts'):
        if not root or not os.path.isdir(root):
            continue
        for dirpath, _dn, fns in os.walk(root):
            for fn in fns:
                index.setdefault(fn.lower(), os.path.join(dirpath, fn))
    for name in names:
        hit = index.get(name.lower())
        if hit:
            return hit
    raise SystemExit('font not found: %s (set --fonts or $LVPS_FONTS)' % (names,))

FONT = _find_font('RussoOne-Regular.ttf')
VENC = ['-c:v', 'libx264', '-preset', 'veryfast' if a.preview else 'slow', '-crf', '23' if a.preview else '16', '-pix_fmt', 'yuv420p', '-r', str(FPS)]
AENC = ['-c:a', 'pcm_s16le', '-ar', str(SR), '-ac', '2']
SC = f'scale={W}:{H}:flags=lanczos,setsar=1'
AF = f'aresample={SR},aformat=sample_fmts=s16:channel_layouts=stereo'


def run(cmd):
    print('>>', ' '.join(cmd)[:240], flush=True)
    subprocess.run(cmd, check=True)


def vdur(p):
    n = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries', 'stream=nb_read_packets',
                        '-of', 'csv=p=0', p], capture_output=True, text=True, check=True).stdout.strip()
    return int(n) / FPS


def dur(p):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p],
                                capture_output=True, text=True, check=True).stdout.strip())


# ---------------------------------------------------------------- cold open part 1: VHS rewind of four Vol. 1 moments
VOL1 = [(os.path.join(L1, 'skit1/skit1_sit_down_1080p.mp4'), 5.5),
        (os.path.join(L1, 'skit2/skit2_eat_that_1080p.mp4'), 3.5),
        (os.path.join(L1, 'skit4/skit4_safety_off_1080p.mp4'), 5.5),
        (os.path.join(L1, 'skit5/skit5_want_some_1080p.mp4'), 5.5)]  # chair, cloche, lever, cake
ins, fv, fa = [], [], []
for i, (p, t0) in enumerate(VOL1):
    ins += ['-ss', str(t0), '-t', '1.0', '-i', p]
    fv.append(f"[{i}:v]scale=1920:1080,fps={FPS},reverse,setpts=0.5*PTS,trim=duration=0.5,setpts=PTS-STARTPTS[c{i}]")
    fa.append(f"[{i}:a]{AF},areverse,atempo=2.0,atrim=duration=0.5,asetpts=PTS-STARTPTS[s{i}]")
vhs_v = (';'.join(fv) + ';' + ''.join(f'[c{i}]' for i in range(4)) + 'concat=n=4:v=1:a=0,'
         "eq=saturation=1.35:contrast=1.1,rgbashift=rh=7:bh=-7,noise=alls=28:allf=t,"
         "drawbox=x=0:y='mod(t*1300\\,1180)-100':w=iw:h=70:color=white@0.22:t=fill,"
         "drawbox=x=0:y=ih-60:w=iw:h=60:color=black@0.55:t=fill,"
         f"drawtext=fontfile='{FONT}':text='<< REW':x=70:y=60:fontsize=84:fontcolor=white:borderw=4:bordercolor=black@0.7,"
         f"drawtext=fontfile='{FONT}':text='PREVIOUSLY ON LITERAL VOICE PACK...':x=70:y=h-52:fontsize=40:fontcolor=0xFFD25A,"
         f"drawtext=fontfile='{FONT}':text='VOL. 1':x=w-tw-70:y=60:fontsize=60:fontcolor=white:borderw=3:bordercolor=black@0.7,"
         f"{SC},format=yuv420p[v]")
vhs_a = (';'.join(fa) + ';' + ''.join(f'[s{i}]' for i in range(4)) + f'concat=n=4:v=0:a=1,volume=-10dB[ra];'
         f"anoisesrc=color=pink:amplitude=0.06:sample_rate={SR}:duration={VHS},{AF},highpass=f=900[hn];"
         f"[ra][hn]amix=inputs=2:normalize=0:duration=first,atrim=0:{VHS},afade=t=in:d=0.08[a]")
vhs_out = os.path.join(TMP, 'cold_vhs.mkv')
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *ins, '-filter_complex', vhs_v + ';' + vhs_a,
     '-map', '[v]', '-map', '[a]', '-t', str(VHS), *VENC, *AENC, vhs_out])

# ---------------------------------------------------------------- cold open part 2: chrome title over the courtroom
tbg = a.title_bg or os.path.join(V2, 'skit5/final_v1/frames/0045.png')
fx = (f"[0:v]scale=2400:1350,zoompan=z='1+0.0012*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={int(TITLE * FPS)}:s=1920x1080:fps={FPS},"
      f"gblur=sigma=3,eq=brightness=-0.14:saturation=0.85,fade=t=in:st=0:d=0.25:color=white[bg];"
      f"[1:v]format=rgba,fade=t=in:st=0.15:d=0.45:alpha=1[ti];"
      f"[2:v]format=rgba,scale=1400:700,colorchannelmixer=aa=0.95[fl];"
      f"[bg][ti]overlay=0:0:format=auto[b1];"
      f"[b1][fl]overlay=x='-1400+(t/1.4)*3300':y=190:enable='lt(t,1.5)',{SC},format=yuv420p[v];"
      f"[3:a]{AF},atrim=0:{TITLE},volume=-10dB,afade=t=in:d=0.25,afade=t=out:st={TITLE - 0.6}:d=0.6[m];"
      f"[4:a]{AF},volume=1dB,adelay=380|380[p];"
      f"[m][p]amix=inputs=2:normalize=0:duration=first,atrim=0:{TITLE}[a]")
title_out = os.path.join(TMP, 'cold_title.mkv')
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-loop', '1', '-t', str(TITLE), '-i', tbg,
     '-loop', '1', '-t', str(TITLE), '-i', os.path.join(GFX, 'title_overlay.png'),
     '-loop', '1', '-t', str(TITLE), '-i', os.path.join(GFX, 'flare.png'),
     '-i', RAZOR, '-i', PROCEED, '-filter_complex', fx, '-map', '[v]', '-map', '[a]', '-t', str(TITLE), *VENC, *AENC, title_out])
cold_out = os.path.join(TMP, 'cold_open.mkv')
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', vhs_out, '-i', title_out, '-filter_complex',
     '[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]', '-map', '[v]', '-map', '[a]', *VENC, *AENC, cold_out])

# ---------------------------------------------------------------- blocks: card + skit
blocks = []
for n in sorted(SKITS):
    src = SKITS[n][0]
    c_out = os.path.join(TMP, f'card_{n}.mkv')
    static_v = ",noise=alls=90:allf=t+u:enable='lt(t,0.3)',eq=brightness=0.06:enable='lt(t,0.3)'" if n == 3 else ''
    fx = (f"[0:v]zoompan=z='1+0.0006*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={int(CARD * FPS)}:s=1920x1080:fps={FPS}"
          f"{static_v},{SC},format=yuv420p[v];"
          f"[1:a]{AF},volume=-6dB,apad,atrim=0:{CARD}[st]")
    if n == 3:   # static burst under the channel switch
        fx += (f";anoisesrc=color=white:amplitude=0.25:sample_rate={SR}:duration=0.3,{AF},afade=t=out:st=0.2:d=0.1,apad,atrim=0:{CARD}[nz];"
               f"[st][nz]amix=inputs=2:normalize=0:duration=first[a]")
    else:
        fx = fx.replace('[st]', '[a]')
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-loop', '1', '-t', str(CARD), '-i', os.path.join(GFX, f'card_{n}.png'),
         '-i', STING, '-filter_complex', fx, '-map', '[v]', '-map', '[a]', '-t', str(CARD), *VENC, *AENC, c_out])
    s_out = os.path.join(TMP, f'skit_{n}.mkv')
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', src, '-vf', f'{SC},fps={FPS},format=yuv420p',
         '-af', AF, *VENC, *AENC, s_out])
    b_out = os.path.join(TMP, f'block_{n}.mkv')
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', c_out, '-i', s_out, '-filter_complex',
         '[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]', '-map', '[v]', '-map', '[a]', *VENC, *AENC, b_out])
    blocks.append((n, b_out, vdur(b_out)))

# ---------------------------------------------------------------- end card (Epic credit) over skit 5's last frame, fades to black
ebg = a.end_bg or os.path.join(V2, 'skit5/final_v1/frames/0390.png')
e_out = os.path.join(TMP, 'end.mkv')
fx = (f"[0:v]scale=1920:1080,zoompan=z='1.04-0.0003*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={int(END * FPS)}:s=1920x1080:fps={FPS},boxblur=2[bg];"
      f"[1:v]format=rgba,fade=t=in:st=0.3:d=0.6:alpha=1[ov];[bg][ov]overlay=0:0,fade=t=out:st={END - 0.8}:d=0.8,{SC},format=yuv420p[v];"
      f"[2:a]{AF},atrim=0:{END},volume=-12dB,afade=t=in:d=0.8,afade=t=out:st={END - 1.5}:d=1.5[a]")
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-loop', '1', '-t', str(END), '-i', ebg,
     '-loop', '1', '-t', str(END), '-i', os.path.join(GFX, 'end_overlay.png'), '-ss', '40', '-i', RAZOR,
     '-filter_complex', fx, '-map', '[v]', '-map', '[a]', '-t', str(END), *VENC, *AENC, e_out])

# post-credits: short black beat, then the stinger (hard cut, like a post-credits scene)
beat_out = os.path.join(TMP, 'beat.mkv')
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'color=c=black:s={W}x{H}:r={FPS}:d={BEAT}',
     '-f', 'lavfi', '-i', f'anullsrc=r={SR}:cl=stereo', '-t', str(BEAT), '-vf', 'format=yuv420p', *VENC, *AENC, beat_out])
st_out = os.path.join(TMP, 'stinger.mkv')
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', STINGER, '-vf', f'{SC},fps={FPS},format=yuv420p', '-af', AF,
     *VENC, *AENC, st_out])

# ---------------------------------------------------------------- xfade chain + concat tail (one encode)
items = [('cold', cold_out, COLD)] + [(n, p, d) for n, p, d in blocks] + [('end', e_out, END)]
inputs, fv, fa = [], [], []
for _, p, _ in items:
    inputs += ['-i', p]
inputs += ['-i', beat_out, '-i', st_out]
acc = items[0][2]
prev_v, prev_a = '0:v', '0:a'
starts = {'cold': 0.0}
for i, (key, p, d) in enumerate(items[1:], start=1):
    offset = acc - XD
    tr, expr = TRANS[key]
    xf = f"transition={tr}" + (f":expr='{expr}'" if expr else '')
    fv.append(f"[{prev_v}][{i}:v]xfade={xf}:duration={XD}:offset={offset:.3f}[v{i}]")
    fa.append(f"[{prev_a}][{i}:a]acrossfade=d={XD}:c1=tri:c2=tri[a{i}]")
    prev_v, prev_a = f'v{i}', f'a{i}'
    starts[key] = offset
    acc = offset + d
nb, ns = len(items), len(items) + 1
starts['stinger'] = acc + BEAT
tail = f"[{prev_v}][{prev_a}][{nb}:v][{nb}:a][{ns}:v][{ns}:a]concat=n=3:v=1:a=1[vout][aout]"
total = acc + BEAT + vdur(st_out)
mix = os.path.join(TMP, 'joined.mkv')
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *inputs, '-filter_complex', ';'.join(fv + fa + [tail]),
     '-map', '[vout]', '-map', '[aout]', *VENC, *AENC, mix])

# ---------------------------------------------------------------- loudnorm (2 pass) -> -14 LUFS, TP -1.5 dBTP
meas = subprocess.run(['ffmpeg', '-hide_banner', '-i', mix, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'],
                      capture_output=True, text=True).stderr
j = json.loads(meas[meas.rindex('{'):meas.rindex('}') + 1])
ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
      f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample={SR}")
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n', '-i', mix, '-map', '0:v', '-map', '0:a', '-c:v', 'copy', '-af', ln,
     '-c:a', 'aac', '-b:a', '256k', '-ar', str(SR), '-movflags', '+faststart', os.path.abspath(a.out)])
wav = os.path.splitext(a.out)[0] + '_mix_48k.wav'
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n', '-i', mix, '-vn', '-af', ln, '-c:a', 'pcm_s16le', '-ar', str(SR), wav])

chap = [{'t': 0.0, 'title': 'Intro'}]
for n in sorted(SKITS):
    chap.append({'t': round(starts[n], 3), 'title': SKITS[n][1]})
chap.append({'t': round(starts['end'], 3), 'title': 'Credits'})
chap.append({'t': round(starts['stinger'], 3), 'title': 'Stinger'})
info = {'duration': round(dur(a.out), 3), 'computed_total': round(total, 3), 'xfade': XD, 'card': CARD, 'cold_open': COLD,
        'end': END, 'beat': BEAT, 'blocks': {str(n): round(d, 3) for n, _, d in blocks}, 'chapters': chap,
        'cuts': {str(k): round(v, 3) for k, v in starts.items()}, 'loudnorm_pass1': j}
with open(os.path.splitext(a.out)[0] + '_chapters.json', 'w') as f:
    json.dump(info, f, indent=1)
print(json.dumps({k: v for k, v in info.items() if k != 'loudnorm_pass1'}, indent=1))

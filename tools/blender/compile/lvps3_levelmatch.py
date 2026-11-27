"""Level-match Vol. 3 skit MP4s to about -14 LUFS / -1.5 dBTP (video stream-copy, audio only re-encoded).
Writes new files only; never overwrites an existing destination or the original finals.
python tools/blender/compile/lvps3_levelmatch.py --root "$LVPS_ROOT" --out-dir DIR
"""
import argparse, json, os, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument('--root', default=os.environ.get('LVPS_ROOT'), help='Vol. 3 render root (or $LVPS_ROOT)')
ap.add_argument('--out-dir', required=True)
ap.add_argument('--target-i', default=-14.0, type=float)
ap.add_argument('--target-tp', default=-1.5, type=float)
a = ap.parse_args()
if not a.root:
    raise SystemExit('set --root or $LVPS_ROOT')
os.makedirs(a.out_dir, exist_ok=True)
V3 = os.path.abspath(a.root)
JOBS = [
    (f'{V3}/skit1/final_v1/skit1_tag_1080p.mp4', 'skit1_tag_1080p_lm.mp4'),
    (f'{V3}/skit2/final_v1/skit2_on_fire_1080p.mp4', 'skit2_on_fire_1080p_lm.mp4'),
    (f'{V3}/skit3/final_v1/skit3_next_1080p.mp4', 'skit3_next_1080p_lm.mp4'),
    (f'{V3}/skit4/final_v1/skit4_cover_me_1080p.mp4', 'skit4_cover_me_1080p_lm.mp4'),
    (f'{V3}/skit5/final_v1/skit5_bow_down_1080p.mp4', 'skit5_bow_down_1080p_lm.mp4'),
]
log = []
for src, name in JOBS:
    dst = os.path.join(a.out_dir, name)
    if os.path.exists(dst):
        print('exists, skip', dst)
        continue
    meas = subprocess.run(['ffmpeg', '-hide_banner', '-i', src,
                           '-af', f'loudnorm=I={a.target_i}:TP={a.target_tp}:LRA=11:print_format=json',
                           '-f', 'null', '-'], capture_output=True, text=True).stderr
    j = json.loads(meas[meas.rindex('{'):meas.rindex('}') + 1])
    print(name, 'in', j['input_i'], 'LUFS', j['input_tp'], 'dBTP', flush=True)
    ln = (f"loudnorm=I={a.target_i}:TP={a.target_tp}:LRA=11:measured_I={j['input_i']}:"
          f"measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
          f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n', '-i', src,
                    '-map', '0:v', '-map', '0:a', '-c:v', 'copy', '-af', ln,
                    '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-movflags', '+faststart', dst], check=True)
    chk = subprocess.run(['ffmpeg', '-hide_banner', '-i', dst,
                          '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    # grab summary
    integ = lra = peak = None
    for line in chk.splitlines():
        if 'I:' in line and 'LUFS' in line and integ is None and 'TARGET' not in line:
            # summary block comes at end; collect last Integrated
            pass
    # parse ebur128 summary
    summary = {}
    # The summary uses "I:" under "Integrated loudness"
    import re
    m = re.findall(r'Integrated loudness:\s+I:\s+([-\d.]+)\s+LUFS', chk)
    tp = re.findall(r'True peak:\s+Peak:\s+([-\d.]+)\s+dBFS', chk)
    rec = {'src': src, 'dst': dst, 'pass1': j, 'out_i': m[-1] if m else None, 'out_tp': tp[-1] if tp else None}
    log.append(rec)
    print('  ->', rec['out_i'], 'LUFS', rec['out_tp'], 'dBTP', os.path.getsize(dst), flush=True)

logp = os.path.join(a.out_dir, 'levelmatch_log.json')
if not os.path.exists(logp):
    json.dump(log, open(logp, 'w'), indent=1)
    print('log', logp)

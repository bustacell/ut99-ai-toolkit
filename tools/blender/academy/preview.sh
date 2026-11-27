#!/bin/sh
# preview.sh CHAPTER "frame,frame,..."  -> low-res build + probe frames + contact sheet
# Use C:/... style paths (Git Bash doesn't convert /c/... paths that contain [ ]).
CH=$1; FR=$2
HERE=$(cd "$(dirname "$0")" && pwd -W 2>/dev/null || pwd)
B=$(python -c "import sys; sys.path.insert(0, r'$HERE/..'); import assetpaths; print(assetpaths.BLENDER)")
W=$(python -c "import sys; sys.path.insert(0, r'$HERE/..'); import assetpaths, os; print(os.path.join(assetpaths.WORK, 'academy', 'preview', '$CH'))")
rm -rf "$W/probe"
"$B" -b -P "$HERE/engine.py" -- $CH "$W" --preview 2>&1 | grep -E 'stage origin|built|Traceback|Error:|line [0-9]+' | grep -v 'Shadow buffer'
"$B" -b "$W/$CH.blend" -o "$W/probe/f####" -f $FR 2>&1 | grep -E 'Traceback|Error' | grep -v 'Shadow buffer'
python - "$W/probe" <<'EOF'
import sys, glob, os
from PIL import Image, ImageDraw
fs = sorted(glob.glob(os.path.join(sys.argv[1], 'f*.png')))
cols = 3
rows = (len(fs) + cols - 1) // cols
s = Image.new('RGB', (cols * 640, rows * 360))
for i, p in enumerate(fs):
    im = Image.open(p).convert('RGB').resize((640, 360))
    ImageDraw.Draw(im).text((8, 8), os.path.basename(p), fill=(255, 255, 0))
    s.paste(im, ((i % cols) * 640, (i // cols) * 360))
s.save(os.path.join(sys.argv[1], 'sheet.jpg'), quality=85)
print(os.path.join(sys.argv[1], 'sheet.jpg'))
EOF

"""Render the checked scene, retain frame progress, then assemble the master."""
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import time

from paths import BLENDER, WORK as ROOT


def stage(value, **details):
    (ROOT/'production-status.json').write_text(json.dumps(dict(stage=value,updated=time.time(),**details),indent=2))


if __name__=='__main__':
    try:
        frames=ROOT/'frames'
        frames.mkdir(exist_ok=True)
        scene=ROOT/'The Other End - Teaser.blend'
        sources=[scene,ROOT/'Brock.pc2',ROOT/'Xan.pc2']
        revision={}
        for source in sources:
            digest=hashlib.sha256()
            with source.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024*1024),b''):
                    digest.update(chunk)
            revision[source.name]=digest.hexdigest()
        receipt=frames/'source.json'
        if any(frames.glob('*.png')) and (not receipt.exists() or json.loads(receipt.read_text())!=revision):
            raise ValueError('The frame cache belongs to a different scene revision. Move it aside before rerendering.')
        receipt.write_text(json.dumps(revision,indent=2))
        if '--finish-only' not in sys.argv:
            stage('rendering')
            with (ROOT/'render.log').open('w',encoding='utf-8') as log:
                subprocess.run([str(BLENDER),'-b',str(scene),'-a'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        stage('encoding')
        subprocess.run([sys.executable,'-u',str(Path(__file__).with_name('finish.py'))],check=True)
        stage('complete')
    except Exception as error:
        stage('failed',error=str(error))
        raise

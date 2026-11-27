"""Original game audio at editorial events with stereo panning and music ducking."""

import json
import math
import subprocess
import wave

import numpy as np

from settings import ROOT
from paths import ASSETS
from timeline import FPS, TOTAL

RATE = 48000
DURATION = TOTAL / FPS
SOUNDS = ASSETS / 'sounds'
MUSIC = ASSETS / 'music'
OUTPUT = ROOT / 'work' / 'Stereo.wav'


def ffmpeg(*args, capture=False):
    result = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', *map(str, args)],
                            check=True, capture_output=capture)
    return result.stdout


def decode(path, length, offset=0, filters=None):
    args = ['-ss', offset, '-i', path, '-t', length]
    if filters:
        args += ['-af', filters]
    raw = ffmpeg(*args, '-ar', RATE, '-ac', 2, '-f', 'f32le', '-', capture=True)
    return np.frombuffer(raw, dtype='<f4').reshape(-1, 2).copy()


def edge(samples, first, last):
    a = min(len(samples), round(first * RATE))
    b = min(len(samples), round(last * RATE))
    if a:
        samples[:a] *= np.linspace(0, 1, a)[:, None]
    if b:
        samples[-b:] *= np.linspace(1, 0, b)[:, None]


class Soundtrack:
    def __init__(self):
        count = int(DURATION * RATE)
        self.music = np.zeros((count, 2), dtype=np.float32)
        self.effects = np.zeros_like(self.music)
        self.duck = np.ones(count, dtype=np.float32)
        self.cues = []

    def add(self, path, start, length, gain, *, offset=0, pan=0, fades=(.012, .075),
            filters=None, music=False, voice=False, automation=None, bed=False):
        samples = decode(path, length, offset, filters)
        first = round(start * RATE)
        samples = samples[:len(self.effects) - first]
        if not len(samples) or np.max(np.abs(samples)) < 1e-5:
            raise ValueError(f'Empty cue from {path}')
        edge(samples, *fades)
        if music or bed:
            samples *= gain / max(.005, float(np.sqrt(np.mean(samples ** 2))))
        else:
            samples *= gain / float(np.max(np.abs(samples)))
        if automation:
            xs, ys = zip(*automation)
            samples *= np.interp(np.arange(len(samples)) / RATE, xs, ys)[:, None]
        samples *= [math.sqrt(1 - pan), math.sqrt(1 + pan)]
        last = first + len(samples)
        target = self.music if music else self.effects
        target[first:last] += samples
        if voice:
            left = min(first, round(.18 * RATE))
            right = min(len(self.duck) - last, round(.32 * RATE))
            envelope = np.r_[np.linspace(1, .42, left), np.full(last - first, .42),
                             np.linspace(.42, 1, right)]
            self.duck[first-left:last+right] = np.minimum(self.duck[first-left:last+right], envelope)
        self.cues.append({'time': round(start, 5), 'duration': round(len(samples)/RATE, 5),
                          'asset': path.name, 'source_offset': offset, 'pan': pan})

    def fx(self, asset, start, length, gain, pan=0, **kwargs):
        self.add(SOUNDS / asset, start, length, gain, pan=pan, **kwargs)

    def voice(self, asset, start, gain=.30, pan=0):
        self.fx(asset, start, 3.1, gain, pan=pan, filters='highpass=f=75,lowpass=f=7600',
                voice=True)

    def wind(self, start, length, level, file='wind21', pan=0):
        self.fx(f'AmbOutside/Looping.{file}.wav', start, length, level, pan=pan,
                fades=(.24, .45), filters='aresample=48000,aloop=loop=-1:size=240000,lowpass=f=1300',
                bed=True)

    def save(self):
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        mix = self.music * self.duck[:, None] + self.effects
        edge(mix, .15, .55)
        scale = min(1.0, .96 / float(np.max(np.abs(mix))))
        stage = OUTPUT.with_suffix('.premaster.wav')
        with wave.open(str(stage), 'wb') as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(RATE)
            audio.writeframes((mix * scale * 32767).astype('<i2').tobytes())
        pending = OUTPUT.with_suffix('.building.wav')
        ffmpeg('-i', stage, '-af', 'loudnorm=I=-15.5:TP=-2:LRA=8', '-ar', RATE,
               '-c:a', 'pcm_s24le', pending)
        pending.replace(OUTPUT)
        stage.unlink()
        (ROOT / 'audio-cues.json').write_text(json.dumps(self.cues, indent=2) + '\n', encoding='utf-8')

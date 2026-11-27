"""An original UT sound edit shared with the picture timeline."""
import json
import math
import subprocess

import numpy as np
import score
from paths import ASSETS, WORK as ROOT

LOCAL=ROOT/'assets'/'audio'
RATE=48000
COUNT=RATE*score.DELIVERY_FRAMES//score.FPS


def decode(source, limit=None, effect=None, start=0):
    args=['ffmpeg','-v','error','-nostdin','-ss',str(start),'-i',str(source)]
    if limit is not None:
        args+=['-t',str(limit)]
    if effect:
        args+=['-af',effect]
    args+=['-ac','2','-ar',str(RATE),'-f','f32le','-']
    return np.frombuffer(subprocess.check_output(args),dtype='<f4').reshape(-1,2).copy()


def taper(samples, attack=.009, release=.05):
    left=min(len(samples),round(RATE*attack))
    right=min(len(samples),round(RATE*release))
    if left:
        samples[:left]*=np.linspace(0,1,left)[:,None]
    if right:
        samples[-right:]*=np.linspace(1,0,right)[:,None]
    return samples


def peak(samples, amplitude):
    return samples * amplitude / max(float(np.abs(samples).max()),.00001)


def mix():
    t=np.arange(COUNT)/RATE
    master=np.zeros((COUNT,2),dtype=np.float32)
    cues=[]

    def put(data,time):
        offset=round(time*RATE)
        length=min(len(data),COUNT-offset)
        if length>0:
            master[offset:offset+length]+=data[:length]

    def one(path,time,amplitude,pan=0,limit=None,fx=None,room=.12,source_start=0):
        source=LOCAL/path if '/' not in path else ASSETS/'sounds'/path
        data=decode(source,limit=limit,effect=fx,start=source_start)
        active=np.flatnonzero(np.max(np.abs(data),axis=1)>.003)
        if len(active):
            data=data[max(0,active[0]-round(.008*RATE)):]
        data=peak(taper(data,attack=.004 if source_start else .009,release=.10 if limit else .05),amplitude)
        data*=np.asarray([math.sqrt(1-pan),math.sqrt(1+pan)])[None,:]
        put(data,time)
        for delay,scale in [(.059,1),(.132,.55),(.221,.33)]:
            put(data[:,::-1]*room*scale,time+delay)
        cues.append(dict(time=round(time,3),asset=source.name,pan=pan,source_start=source_start))

    for file,level,fx,roll in [('Fan2.wav',.042,'lowpass=f=1850',.8),('hum11.wav',.029,'lowpass=f=420',.4)]:
        tone=decode(LOCAL/file,effect=fx)
        length=len(tone)
        # Overlap loop seams so the room remains continuous across picture cuts.
        n=min(round(.075*RATE),length//4)
        loop=tone[:-n].copy()
        loop[:n]=tone[:n]*np.linspace(0,1,n)[:,None]+tone[-n:]*np.linspace(1,0,n)[:,None]
        tone=np.tile(loop,(math.ceil(COUNT/len(loop)),1))[:COUNT]
        ambience=np.interp(t,[0,9.45,10.1,12.18,12.5,13.4,15.85,16.2,score.END_CARD,score.DELIVERY_DURATION],[1,1,.36,.27,.06,.79,.58,.21,.67,0])
        master+=peak(tone,.065*level/.042)*ambience[:,None]*roll

    music_path=ASSETS/'music'/'Godown.wav'
    music=decode(music_path,score.DELIVERY_DURATION,start=0)
    low=decode(music_path,score.DELIVERY_DURATION,effect='lowpass=f=700',start=0)
    opening=np.interp(t,[0,2.25,7.5,9.5,12.20,15.85,16.7,score.END_CARD,score.DELIVERY_DURATION],[.07,.08,.21,.12,.0,.04,.28,.72,1])[:,None]
    volume=np.interp(t,[0,2.2,4.55,7,8.75,9.75,12.20,13.4,15.85,16.7,score.END_CARD,20.95,score.DELIVERY_DURATION],[.18,.33,.11,.43,.61,.27,.08,.04,.08,.20,.54,.59,0])[:,None]
    master+=(low*(1-opening)+music*opening)*volume*.26

    one('mclang2.wav',.67,.12,.36,fx='lowpass=f=2400',room=.26)
    one('steam3.wav',2.1,.081,-.34,limit=1.2,room=.26)
    one('BossVoice/(All).Brunhuman.wav',4.57,.45,.08,fx='highpass=f=74,lowpass=f=9200',room=.23)
    for contact,pan in zip(score.XAN_FOLEY_FRAMES,(.12,-.12)):
        one('Botpack/Boss.BFootstep.wav',score.seconds(contact),.32,pan,limit=.34,room=.14,source_start=.176)
    one('Loading.wav',7.79,.18,.26,room=.16)
    one('EightAltFire.wav',score.ROCKET_LAUNCH,.45,.35,room=.24)
    one('Botpack/RocketLauncher.RocketFly1.wav',9.12,.23,.39,fx='aresample=48000,asetrate=22000,aresample=48000',room=.14)
    one('Botpack/Translocator.ThrowTarget.wav',score.DISC_LAUNCH,.29,-.31,room=.21)
    one('Botpack/RocketLauncher.RocketFly1.wav',11.71,.34,-.35,room=.10,
        fx='aresample=48000,asetrate=41000,aresample=48000')
    one('Botpack/RocketLauncher.RocketFly1.wav',score.ROCKET_DOOR-.09,.13,-.09,limit=.72,room=.19,
        fx='aresample=48000,asetrate=33000,aresample=48000,lowpass=f=1600')
    one('mclang2.wav',score.DISC_LANDING,.19,.09,limit=.29,room=.20)
    hum=decode(ASSETS/'sounds'/'Botpack/Translocator.targethum.wav')
    need=round((score.WARP-13.44)*RATE)
    hum=np.tile(hum,(math.ceil(need/len(hum)),1))[:need]
    put(peak(taper(hum,.20,.12),.11),13.44)
    cues.append(dict(time=13.44,asset='Translocator.targethum.wav',pan=0))
    one('Botpack/Translocator.TDisrupt.wav',score.WARP-.21,.18,.10,limit=.42,room=.24)
    one('Botpack/Translocator.ReturnTarget.wav',score.WARP,.67,0,room=.24)
    one('Botpack/General.Explg02.wav',score.WARP+.018,.27,0,limit=.44,fx='lowpass=f=190',room=.13)
    face_time = score.TITLE
    coret_time = face_time + score.MONTAGE[0][1] / score.FPS
    roof_time = coret_time + score.MONTAGE[1][1] / score.FPS
    one('AmbOutside/Looping.wind21.wav',face_time,.16,.25,limit=.88,
        fx='lowpass=f=1300',room=.10)
    one('mclang2.wav',coret_time+.09,.20,-.26,limit=.61,
        fx='aresample=48000,asetrate=35000,aresample=48000,lowpass=f=1500',room=.25)
    one('AmbOutside/Looping.wind23.wav',roof_time,.17,-.18,limit=.94,
        fx='highpass=f=100,lowpass=f=3150',room=.10)

    raw=ROOT/'soundtrack.f32'
    raw.write_bytes(taper(master,.05,.55).astype('<f4').tobytes())
    args=['ffmpeg','-hide_banner','-nostdin','-f','f32le','-ar',str(RATE),'-ac','2','-i',str(raw)]
    result=subprocess.run([*args,'-af','loudnorm=I=-16:TP=-1.5:LRA=10:print_format=json','-f','null','NUL'],check=True,capture_output=True,text=True)
    measured=json.JSONDecoder().raw_decode(result.stderr[result.stderr.rfind('{'):])[0]
    filt='loudnorm=I=-16:TP=-1.5:LRA=10:linear=true'
    for out,key in [('measured_I','input_i'),('measured_TP','input_tp'),('measured_LRA','input_lra'),('measured_thresh','input_thresh'),('offset','target_offset')]:
        filt+=f':{out}={measured[key]}'
    subprocess.run([*args,'-v','error','-y','-af',filt,'-ar',str(RATE),'-c:a','pcm_s24le',str(ROOT/'soundtrack.wav')],check=True)
    raw.unlink()
    (ROOT/'audio-cues.json').write_text(json.dumps({'music':'Godown, original Deck16 music','cues':cues,'master':measured},indent=2))


if __name__=='__main__':
    mix()

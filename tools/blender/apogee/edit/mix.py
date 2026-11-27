"""Narrative stereo mix, with stock UT sounds tied to selected source frames."""
from audio import MUSIC, Soundtrack
from timeline import FPS, TOTAL, hit, time


def mix():
    sound = Soundtrack()
    fx, voice = sound.fx, sound.voice

    def stock(path, when, length, gain, pan=0, **kwargs):
        fx(f'UnrealShare/{path}', when, length, gain, pan, **kwargs)

    def music(path, start, end, level, offset=0, fades=(.45,.5), automation=None):
        sound.add(MUSIC / path, start, end-start, level, offset=offset,
                  fades=fades, music=True, automation=automation)

    # Let each location retain a little of its own air. Duck the score under
    # the original voice packs and give the main hits room above the music.
    opening_end = time('deck-establish', .46)
    music('Foregone.wav', 0, opening_end, .110, offset=45.418-time('main-title'),
          fades=(.02,.44), automation=[(0,.20),(1.1,.42),(3.39,.08),(3.67,1.12),
                                      (7.55,.52),(12,.82),(15.625,1.04),(24.8,.98)])
    deck = time('deck-establish') - .15
    music('Godown.wav', deck, time('morpheus-vista',.25), .108, offset=18.65,
          fades=(.5,.43), automation=[(0,.63),(3.4,.58),(5.8,.78),(8.6,.50),
                                      (11.4,.84),(14.5,.26),(15.8,.12),(16.3,1.15)])
    morph = time('morpheus-vista')
    music('Foregone.wav', morph-.17, time('hyperblast-arrival',.33), .108,
          offset=69.079-(time('morpheus-launch')-morph)-.17,
          fades=(.40,.69), automation=[
              (0,.65),(4,.72),(6.6,.35),(8.2,1.06),(10.9,.45),(13.4,.79),
              (18.8,1.01),(24.0,.88),(25.5,.38),(28,.62),(33.0,.21),
              (34.3,.90),(37.8,.92),(40.6,1.15),(42.2,.68),(45.7,.48)])
    hyper = time('hyperblast-arrival') - .08
    music('Uttitle.it', hyper, TOTAL/FPS, .122, offset=4.4, fades=(.55,1.05),
          automation=[(0,.42),(3.1,.59),(6.5,.64),(9,.47),(12.1,.70),
                      (14.9,.52),(15.7,1.12),(20,.95),(22.54,.64)])

    stock('Eightball.Ignite.wav', 0, .65, .40, -.17)
    fx('Botpack/RocketLauncher.RocketFly1.wav', .17, .94, .19, .36)
    stock('General.Expl03.wav', hit('cold-combo',178), .75, .46, -.18)
    stock('General.Explo1.wav', hit('cold-gap',308), 1.14, .52, .32)
    sound.wind(time('main-title'), 8.35, .023, 'wind21')
    voice('Announcer/(All).prepare.wav', time('return-to-tower',.45), .40)
    fx('Botpack/Generic.RespawnSound2.wav', time('respawn',.05), .77, .20)
    fx('AmbModern/Looping.mclang2.wav', time('riker-ready',.74), .76, .16, -.34)
    fx('Botpack/ASMD.TazerSelect.wav', time('riker-ready',.30), .6, .24, -.18)
    fx('AmbModern/Looping.Fan2.wav', time('anna-ready'), 1.7, .026, -.12, bed=True)

    fx('Botpack/CTF.flagtaken.wav', hit('flag-in-sight',27), .90, .38, .06)
    voice('Male1Voice/(All).M1igotflag.wav', time('flag-taken',.07), .34, -.12)
    fx('Botpack/ASMD.TazerFire.wav', hit('covering-fire',96), .44, .29, -.31)
    fx('Botpack/PulseGun.PulseFire.wav', hit('covering-fire',119), .41, .24, .37)
    for name, pos in [('flag-taken',.35),('flag-taken',.86),('flag-taken',1.25),
                      ('into-deck',.14),('into-deck',.68),('deck-pursuit',.22),
                      ('deck-pursuit',.63),('duck-behind-cover',.55)]:
        fx('MaleSounds/(All).land01.wav', time(name,pos), .21, .10, -.17,
           filters='highpass=f=125,lowpass=f=4100')
    fx('Botpack/General.Expl04.wav', time('dodge',.41), .92, .32, .33)
    fx('MaleSounds/(All).land01.wav', time('dodge',.83), .30, .17, -.22)
    fx('Botpack/ASMD.TazerFire.wav', time('deck-pursuit',.66), .44, .24, .33)

    fx('AmbModern/Looping.steam3.wav', time('deck-establish',.85), .92, .13, -.24)
    voice('BossVoice/(All).Brunhuman.wav', time('xan-warning',.07), .36, .14)
    for frame in (128,142):
        fx('Botpack/Boss.BFootstep.wav', hit('xan-warning',frame), .52, .21,
           offset=.176, pan=.19)
    stock('Eightball.Loading.wav', time('brock-translocator',.97), .59, .17, -.15)
    stock('Eightball.EightAltFire.wav', hit('deck-launch',214), .7, .37, .34)
    fx('Botpack/Translocator.ThrowTarget.wav', hit('deck-launch',226), .69, .28, -.28)
    fx('Botpack/RocketLauncher.RocketFly1.wav', time('crossed-projectiles',.33),
       2.8, .22, .17, filters='aresample=48000,aloop=loop=-1:size=28800')
    fx('AmbModern/Looping.mclang2.wav', hit('rocket-through-door',317), .69, .18, -.13)
    fx('Botpack/Translocator.targethum.wav', time('disc-lands',.10), 1.54, .11,
       filters='aresample=48000,aloop=loop=-1:size=18800')
    fx('Botpack/Translocator.ReturnTarget.wav', hit('telefrag',382), .83, .39)
    stock('General.Explo1.wav', time('brock-after-flash',.02), 1.29, .38, .07)

    sound.wind(time('morpheus-vista'), time('lava-reveal')-time('morpheus-vista'), .026, 'wind04',.15)
    for frame in (129,146,158):
        fx('Botpack/Boss.BFootstep.wav', hit('xan-aims',frame), .38, .15,
           offset=.16, pan=.33)
    fx('FemaleSounds/(All).stone05.wav', time('lauren-runs',.08), .23, .16, -.25)
    fx('FemaleSounds/(All).stone02.wav', time('lauren-clears-post',.09), .23, .18, -.20)
    stock('Eightball.Ignite.wav', hit('morpheus-launch',187), .75, .40, .28)
    fx('FemaleSounds/(All).Fjump1.wav', time('takeoff',.015), .56, .26, -.20)
    fx('Botpack/RocketLauncher.RocketFly1.wav', time('morpheus-launch',.14),
       time('morpheus-hit')-time('morpheus-launch',.14), .18, .33, fades=(.05,.07),
       filters='aresample=48000,aloop=loop=-1:size=23750,lowpass=f=3100')
    fx('FemaleSounds/(All).lland1.wav', hit('landing-wide',301), .62, .29, -.29)
    stock('General.Explo1.wav', hit('morpheus-hit',307), 1.35, .62, .34)
    fx('FemaleSounds/(All).stone05.wav', time('lauren-recovers',.24), .24, .14, -.23)

    fx('AmbOutside/Looping.gyser1.wav', time('lava-reveal'), 6.4, .035, .09,
       filters='aresample=48000,aloop=loop=-1:size=125000,lowpass=f=1300', bed=True)
    for frame in (17,33,50):
        fx('Botpack/Boss.BFootstep.wav', hit('xan-on-lava',frame), .42, .22, offset=.156)
    for frame in (96,101,107):
        stock('Eightball.Ignite.wav', hit('salvo',frame), .49, .24, .21)
    fx('Botpack/RocketLauncher.RocketFly1.wav', hit('salvo',98), 1.21, .18, .38)

    sound.wind(time('cover-her'), 8.2, .021, 'wind21', -.14)
    voice('Female1Voice/(All).F1gotyourb.wav', time('cover-her',.67), .39, -.14)
    fx('Botpack/SniperRifle.SniperFire.wav', hit('tower-signal',87), .57, .23, .3,
       filters='lowpass=f=1950')
    fx('Botpack/ASMD.TazerAltFire.wav', time('asmd-build',.16), .46, .23, -.32)
    fx('Botpack/ASMD.TazerFire.wav', hit('asmd-discharge',175), .47, .41, .14)
    stock('General.Expl03.wav', hit('asmd-discharge',178), 1.03, .60, .04)
    fx('Botpack/RocketLauncher.RocketFly1.wav', time('flag-rocket-near-miss',.23), 1.11, .24, .39)
    fx('Botpack/ASMD.TazerAltFire.wav', hit('lauren-aims',119), .60, .28, -.30)
    fx('Botpack/ASMD.TazerFire.wav', hit('lauren-aims',137), .52, .33, -.25)
    stock('General.Expl03.wav', hit('lauren-combo',138), 1.22, .58, .15)
    fx('Botpack/CTF.CaptureSound.wav', hit('flag-capture',209), 1.23, .40)
    voice('Announcer/(All).capture.wav', time('flag-release',.08), .44)

    fx('AmbModern/Looping.Fan2.wav', time('hyperblast-arrival'), time('visor')-time('hyperblast-arrival'),
       .023,.1,bed=True, fades=(1.0,.40),filters='aresample=48000,aloop=loop=-1:size=138000,lowpass=f=1570')
    fx('Botpack/Generic.RespawnSound2.wav', hit('malcolm-materializes',183), .78, .28, .12)
    for frame in (238,251,264):
        fx('MaleSounds/(All).land01.wav', hit('malcolm-approaches',frame), .23, .13, .17)
    voice('BossVoice/(All).Bomega.wav', time('alpha-and-omega',.05), .39, -.14)
    voice('Male1Voice/(All).M1letsrock.wav', time('lets-rock',.28), .37, .14)
    stock('Eightball.Loading.wav', hit('visor',457), .57, .18, -.12)
    stock('Eightball.Ignite.wav', hit('hyperblast-fire',484), .95, .61, -.14)
    stock('Menu.Select4.wav', time('channel-outro',.52), .47, .21)
    sound.save()


if __name__ == '__main__':
    mix()

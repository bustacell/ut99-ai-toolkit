"""Picture edit, source frame ranges and the shared picture/sound clock."""
from dataclasses import dataclass

FPS = 24


@dataclass(frozen=True)
class Shot:
    name: str
    source: str
    first: int
    last: int
    seconds: float
    crop: float = 1.0
    aim: tuple[float, float] = (.5, .5)
    graphic: str = ''

    @property
    def frames(self):
        return round(self.seconds * FPS)

    @property
    def selection(self):
        return self.last - self.first + 1


SHOTS = [
    # Cold open. Quick silhouettes and one full impact before the title.
    Shot('cold-rocket', 'morpheus', 187, 195, .375, .95, (.38,.44)),
    Shot('cold-lava', 'lava', 30, 44, .625),
    Shot('cold-flight', 'morpheus', 236, 254, .8, .91, (.66,.46)),
    Shot('cold-visage', 'hyperblast', 302, 320, .8, .88, (.50,.34)),
    Shot('cold-combo', 'combo', 174, 188, .625),
    Shot('cold-gap', 'morpheus', 308, 318, .465),
    Shot('main-title', 'signal', 10, 107, 4.0, graphic='title'),
    Shot('return-to-tower', 'signal', 111, 172, 2.0, .95, (.69,.4)),
    Shot('respawn', 'malcolm', 2, 63, 2.0, .94, (.5,.45)),
    Shot('riker-ready', 'liandri', 63, 128, 2.25, .93, (.52,.49)),
    Shot('anna-ready', 'phobos', 85, 135, 1.7, .96, (.51,.42)),

    Shot('flag-in-sight', 'coret', 1, 38, 1.58, graphic='take'),
    Shot('flag-taken', 'coret', 39, 90, 1.92, .97, (.41,.44)),
    Shot('covering-fire', 'coret', 94, 135, 1.62),
    Shot('into-deck', 'chase', 6, 41, 1.38),
    Shot('dodge', 'chase', 45, 68, 1.0),
    Shot('deck-pursuit', 'chase', 73, 112, 1.5),
    Shot('duck-behind-cover', 'chase', 119, 158, 1.58, .94),
    Shot('deck-establish', 'deck', 1, 51, 2.04),
    Shot('brock-listens', 'deck', 60, 105, 1.83, .93, (.47,.47)),
    Shot('xan-warning', 'deck', 111, 161, 2.08),
    Shot('brock-translocator', 'deck', 167, 202, 1.5, .93, (.4,.53)),
    Shot('deck-launch', 'deck', 205, 228, 1.0),
    Shot('crossed-projectiles', 'deck', 229, 272, 1.83),
    Shot('rocket-through-door', 'deck', 274, 320, 1.58),
    Shot('disc-lands', 'deck', 326, 369, 1.83, .94, (.55,.62)),
    Shot('telefrag', 'deck', 371, 383, .54),
    Shot('brock-after-flash', 'brock', 385, 442, 2.4, .98),

    Shot('morpheus-vista', 'morpheus-wide', 3, 63, 2.54, graphic='jump'),
    Shot('lauren-looks', 'morpheus-wide', 67, 116, 1.98, .94, (.51,.5)),
    Shot('xan-aims', 'morpheus-wide', 125, 158, 1.25, .92),
    Shot('lauren-runs', 'morpheus-wide', 167, 175, .375),
    Shot('lauren-clears-post', 'morpheus', 176, 186, .42),
    Shot('morpheus-launch', 'morpheus', 187, 195, .375),
    Shot('takeoff', 'morpheus', 196, 231, 1.33),
    Shot('apex', 'morpheus', 232, 272, 1.70, .94, (.58,.48)),
    Shot('landing-wide', 'morpheus', 273, 306, 1.38),
    Shot('morpheus-hit', 'morpheus', 307, 318, .5),
    Shot('lauren-recovers', 'morpheus', 319, 337, .8, .94, (.58,.41)),
    Shot('phobos-orbit', 'phobos', 4, 77, 3.08),
    Shot('lava-reveal', 'lava', 4, 105, 3.75),
    Shot('molten-channel', 'lava', 114, 186, 2.75, .93, (.68,.66)),
    Shot('xan-on-lava', 'squad', 6, 53, 1.77, .96),
    Shot('salvo', 'squad', 88, 135, 1.70),

    Shot('cover-her', 'overlook', 9, 70, 2.58, .95, (.53,.42), 'home'),
    Shot('tower-signal', 'overlook', 79, 126, 1.96),
    Shot('malcolm-breaks', 'overlook', 137, 187, 1.98, .95),
    Shot('asmd-build', 'combo', 121, 173, 2.21, .92, (.38,.46)),
    Shot('asmd-discharge', 'combo', 174, 198, 1.04),
    Shot('from-the-blast', 'capture', 1, 53, 2.08),
    Shot('flag-rocket-near-miss', 'capture', 82, 116, 1.25),
    Shot('lauren-aims', 'capture-fx', 118, 137, .83, .98),
    Shot('lauren-combo', 'capture-fx', 138, 168, 1.29),
    Shot('final-run', 'capture', 177, 198, .92),
    Shot('flag-capture', 'capture', 199, 225, 1.125),
    Shot('flag-release', 'capture', 227, 280, 2.25),

    Shot('hyperblast-arrival', 'hyperblast', 12, 97, 3.58),
    Shot('xan-silhouette', 'hyperblast', 121, 163, 1.75, .93, (.53,.39)),
    Shot('malcolm-materializes', 'hyperblast', 181, 207, 1.125),
    Shot('malcolm-approaches', 'hyperblast', 233, 269, 1.54, .92),
    Shot('alpha-and-omega', 'hyperblast', 276, 340, 2.70, .95, (.5,.38)),
    Shot('lets-rock', 'hyperblast', 346, 394, 2.04, .92, (.57,.39)),
    Shot('visor', 'hyperblast', 424, 474, 2.12, .90, (.51,.38)),
    Shot('hyperblast-fire', 'hyperblast', 475, 488, .58),
    Shot('channel-outro', 'signal', 27, 106, 7.0, graphic='outro'),
]

INDEX = {shot.name: shot for shot in SHOTS}
START = {}
frames = 0
for shot in SHOTS:
    START[shot.name] = frames
    frames += shot.frames
TOTAL = frames


def time(name, offset=0):
    return START[name] / FPS + offset


def hit(name, source_frame):
    shot = INDEX[name]
    if not shot.first <= source_frame <= shot.last:
        raise ValueError(f'{name}: cue is outside the source range')
    return time(name, (source_frame - shot.first) * shot.frames / shot.selection / FPS)

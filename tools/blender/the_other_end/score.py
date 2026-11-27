"""The Other End. World-space blocking and edit, measured against Deck16."""

FPS = 24
DURATION = 20
FLOOR = -15.36
BROCK = (18.62, -16.42, FLOOR)
XAN = (18.02, -8.38, FLOOR)
TARGET = (18.02, -8.94, FLOOR + .043)
ROCKET_LAUNCH = 8.875
DISC_LAUNCH = 9.375
ROCKET_DOOR = 12.79
ROCKET_EXIT = 13.67
ROCKET_DESTINATION = (17.20, -24.75, -13.46)
DISC_LANDING = 13.17
WARP = 15.875
TITLE = 383 / FPS
MONTAGE = (('face', 22), ('coret', 19), ('morpheus', 23))
MONTAGE_FRAMES = sum(count for _, count in MONTAGE)
END_CARD = TITLE + MONTAGE_FRAMES / FPS
DELIVERY_FRAMES = FPS * DURATION + MONTAGE_FRAMES
DELIVERY_DURATION = DELIVERY_FRAMES / FPS
XAN_STEPS = ((4.72, 5.00, 5.33), (5.26, 5.54, 5.88))
XAN_FOLEY_FRAMES = (128, 142)


def seconds(frame):
    return (frame-1)/FPS

# In/out points, camera positions, sightline, focal length and aperture.
# All cameras stay on the east side of the action axis.
SHOTS = [
    ('01  A familiar room', 0, 2.25, (9.8,-6,-17.0), (10.57,-5.78,-16.79), (21,7,-21), 22, 9),
    ('02  Listen', 2.25, 4.5, (20.77,-14.64,-13.73), (20.27,-14.72,-13.75), (18.61,-16.40,-14.00), 61, 4.5),
    ('03  Run, human', 4.5, 6.83, (20.0,-11.90,-14.76), (19.78,-11.7,-14.66), (18.03,-8.79,-14.54), 39, 5.6),
    ('04  The choice', 6.83, 8.5, (19.75,-15.37,-14.14), (19.54,-15.31,-14.11), (18.97,-16.21,-14.12), 53, 5),
    ('05  Rocket', 8.5, 9.5, (19.86,-6.49,-13.72), (19.94,-6.54,-13.69), (18.6,-15.88,-14.31), 33, 8),
    ('06  Crossed paths', 9.5, 11.375, (22.05,-13.52,-13.80), (20.94,-13.82,-13.94), (18.23,-13.80,-14.12), 33, 6.3),
    ('07  Through the door', 11.375, 13.5, (21.25,-12.48,-13.72), (21.03,-12.69,-13.76), (20.24,-19.08,-14.03), 27, 7.1),
    ('08  At his feet', 13.5, 15.42, (18.94,-10.46,-15.03), (18.82,-10.23,-15.01), TARGET, 66, 5.6),
    ('09  The discharge', 15.42, TITLE, (21.39,-11.06,-13.92), (20.99,-10.92,-13.89), (18.02,-8.94,-14.29), 48, 6.3),
    ('10  Title over Deck16', TITLE, DURATION, (22.03,-17.22,-13.0), (22.36,-17.7,-12.87), (17.94,-8.94,-15.10), 24, 8),
]

PROBES = [18, 70, 143, 181, 217, 255, 300, 339, 374, 382, 420, 455]

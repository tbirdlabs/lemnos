# Fireflies's card, for the board's game picker (gamehost/lobby.py): a few fireflies, one cluster glowing together. Kept apart from the game so the
# picker can show it without loading the game (the colors are game.py's).

OFF = (0, 0, 0)
GLOW = (170, 255, 20)


def draw(lights, now):
    for t, i, k in (("B2", 0, 1.0), ("B2", 2, 0.8), ("C2", 1, 1.0), ("C3", 0, 0.7), ("E5", 1, 0.3), ("F2", 2, 0.5),
                    ("D6", 0, 0.2), ("A3", 1, 0.4)):
        c = [OFF, OFF, OFF]
        c[i] = (int(GLOW[0] * k), int(GLOW[1] * k), int(GLOW[2] * k))
        lights.spot(t, c)

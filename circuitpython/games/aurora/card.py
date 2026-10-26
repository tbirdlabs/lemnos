# Aurora's card, for the board's game picker (gamehost/lobby.py): one curtain, green below to violet above. Kept apart from the game so the
# picker can show it without loading the game (the colors are game.py's).

from gamehost import geometry as G

OFF = (0, 0, 0)
EDGE = (30, 255, 80)
MIDDLE = (0, 170, 150)
HIGH = (110, 40, 210)


def draw(lights, now):
    for t in range(G.SPOTS):
        r = G.ROW[t]
        c = (EDGE, EDGE, MIDDLE, HIGH, OFF, OFF, OFF)[6 - r] if r >= 2 else OFF
        lights.spot(t, [(c[0] // 2, c[1] // 2, c[2] // 2)] * 3 if r == 6 else [c] * 3)

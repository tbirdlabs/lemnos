# The clock's card, for the board's game picker (gamehost/lobby.py): the face at ten past ten. Kept apart from the game so the
# picker can show it without loading the game (the colors are game.py's).

from gamehost import geometry as G

FACE = (6, 8, 24)
HUB = (110, 90, 60)
HOUR = (0, 0, 255)
MINUTE = (0, 255, 0)


def draw(lights, now):
    for t in range(G.SPOTS):
        if max(abs(G.Q[t]), abs(G.R[t]), abs(G.Q[t] + G.R[t])) < 3:
            lights.spot(t, [FACE] * 3)
    lights.spot(G.CENTER, [HUB] * 3)
    lights.spot("C3", [HOUR] * 3)
    for t in ("C4", "B4"):
        lights.spot(t, [MINUTE] * 3)

# Forest fire's card, for the board's game picker (gamehost/lobby.py): forest with a fire in it. Kept apart from the game so the
# picker can show it without loading the game (the colors are game.py's).

from gamehost import geometry as G

OFF = (0, 0, 0)
FOREST = ((0, 0, 0), (40, 150, 10), (0, 130, 20), (0, 110, 30))
LIT = ((False, False, False), (False, True, False), (True, False, True), (True, True, True))
FIRE_HOT = (255, 110, 0)
EMBER = (50, 6, 0)


def draw(lights, now):
    for t in range(G.SPOTS):
        n = 1 + (G.Q[t] * 7 + G.R[t] * 3) % 3
        lights.spot(t, [FOREST[n] if LIT[n][i] else OFF for i in range(3)])
    for t in ("C3", "D4", "D3"):
        lights.spot(t, [FIRE_HOT] * 3)
    lights.spot("C4", [EMBER] * 3)

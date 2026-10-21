# Island Rush's card, for the board's game picker (gamehost/lobby.py): the jungle thickening toward the taco truck,
# a tiger in it and a player setting out from a corner. Kept apart from the game so the picker can show it without
# loading the game.

from gamehost import fx
from gamehost import geometry as G

JUNGLE = (0, 70, 8)
TRUCK = (200, 200, 200)
TIGER = (255, 90, 0)
PLAYER = (255, 20, 20)
LIT = ((False, False, False), (False, True, False), (True, False, True), (True, True, True))


def draw(lights, now):
    for t in range(G.SPOTS):
        d = max(abs(G.Q[t]), abs(G.R[t]), abs(G.Q[t] + G.R[t]))
        if d:
            lights.spot(t, [JUNGLE if on else (0, 0, 0) for on in LIT[4 - d]])
    lights.spot(G.CENTER, [TRUCK] * 3, fx.breathe(2.5, low=0.25))
    lights.spot("C3", [TIGER] * 3, fx.chase(1.2, tail=1))
    lights.spot(G.SIDES[1][0], [PLAYER] * 3)

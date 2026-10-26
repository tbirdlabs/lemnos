# Rain's card, for the board's game picker (gamehost/lobby.py): the pond, with a drop's ring around the middle and a fainter one inside it (no bright
# middle: that looks like the picker's own blinking white hex). Kept apart from the game so the
# picker can show it without loading the game (the colors are game.py's).

from gamehost import geometry as G

POND = (0, 10, 32)
RIPPLE = (140, 190, 255)
LEVELS = 64


def level(i):
    """game.py's COLORS[i]: i of LEVELS - 1 steps from the still pond to a full ring."""
    return tuple(POND[k] + (RIPPLE[k] - POND[k]) * i // (LEVELS - 1) for k in range(3))


def draw(lights, now):
    rings = (level(0), level(LEVELS // 3), level(LEVELS - 1), level(0))
    for t in range(G.SPOTS):
        lights.spot(t, [rings[max(abs(G.Q[t]), abs(G.R[t]), abs(G.Q[t] + G.R[t]))]] * 3)

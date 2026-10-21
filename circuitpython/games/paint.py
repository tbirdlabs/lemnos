# Paint: the smallest whole game, as an example to copy, and a quick test of the board's lights and controllers.
#
# Every controller gets a cursor in its seat's color, starting on its own side of the island. Move / move back step
# the cursor through the spots (far row first, left to right, as that player sees them) and the arrows move it
# directly; pick paints the spot in your color, or clears it if it's already yours; back clears all your paint.
# Your bar shows how many spots you've painted. A one-switch controller (move and pick only) can play all of it
# except clearing everything at once. On the small board, the line between two hexes of the same color lights in
# that color too (and a row's end line, when the hex at that end is painted), so painted areas join up.
#
# Everything a game needs is here: subclass Game, react to event(), draw() each frame, and use geometry for the
# board's shape. No pins and no strips: this file runs the same on any wiring and with any controller.

from gamehost import fx
from gamehost import geometry as G
from gamehost.game import Game as BaseGame

OFF = (0, 0, 0)
DIM = (36, 36, 36)
COLORS = (None, (255, 30, 20), (255, 190, 0), (0, 200, 60), (0, 200, 200), (30, 90, 255), (200, 40, 255))  # by seat
CURSOR = fx.flash(0.6)                   # the spot under a cursor flashes white
TOUCHING = [G.line_spots(k) for k in range(G.LINES)]     # the one or two hexes beside each line


def card(lights, now):
    """The board's game picker shows this (gamehost/lobby.py): a few painted patches."""
    for k, t in enumerate(("C2", "C3", "D3", "D5", "E4", "E5", "B4", "F2")):
        lights.spot(t, [COLORS[k % 6 + 1]] * 3)


class Player:
    def __init__(self, controller):
        self.seat = controller.seat or 1
        self.view = G.VIEWS[self.seat]
        self.color = COLORS[self.seat]
        self.cursor = G.SIDES[self.seat][1]       # on their own side


class Game(BaseGame):
    def __init__(self, board):
        BaseGame.__init__(self, board)
        self.players = {}                         # controller -> Player
        self.paint = [None] * G.SPOTS             # each spot's color, or None

    def controller_added(self, controller, now):
        self.players[controller] = Player(controller)

    def controller_removed(self, controller, now):
        self.players.pop(controller, None)

    def event(self, controller, action, now):
        p = self.players.get(controller)
        if p is None:
            return
        if action in ("move", "move_back"):
            k = p.view.order[p.cursor] + (1 if action == "move" else -1)
            p.cursor = p.view.reading[k % G.SPOTS]
        elif action in ("up", "down", "left", "right"):
            t = p.view.arrow(p.cursor, action)
            if t != G.ON_BAR:                     # this game has nothing to pick on the bar
                p.cursor = t
        elif action == "pick":
            t = p.cursor
            self.paint[t] = None if self.paint[t] == p.color else p.color
        elif action == "back":
            self.paint = [None if c == p.color else c for c in self.paint]

    def draw(self, lights, now):
        for t in range(G.SPOTS):
            if self.paint[t]:
                lights.spot(t, [self.paint[t]] * 3)
        if lights.has_lines:
            for k in range(G.LINES):
                beside = [self.paint[t] for t in TOUCHING[k]]
                if beside[0] and beside.count(beside[0]) == len(beside):
                    lights.line(k, beside[0])
        for p in self.players.values():
            under = self.paint[p.cursor] or DIM
            lights.spot(p.cursor, [under] * 3, CURSOR)
            n = sum(1 for c in self.paint if c == p.color)
            lights.bar(p.seat, [p.color if i < n else OFF for i in range(G.BAR_LEDS)])

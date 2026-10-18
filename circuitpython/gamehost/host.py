# The game host: runs one game on the board. It owns the lights and the controllers; the game owns everything else.
# The interface a game sees is in game.py; how a game is found is load_game() below.
#
#   from gamehost import host
#   host.run()                  # the game config.GAME names, forever (code.py does this at power-up)
#   host.run("paint")           # another one
#
# Nothing in the host changes for a new game, a new input device or a new LED driver.

import time
import config
from . import geometry
from .controls import Controls, ADDED
from .lights import Lights, OFF


class Board:
    """What a game is given (as Game.board).

    lights        lights.Lights: draw with spot(), bar(), line()
    controls      controls.Controls
    controllers   the controllers connected right now (controls.Controller)
    seats         6, numbered 1-6 clockwise from the bottom
    """

    def __init__(self, lights=None, controls=None):
        """lights, controls: made from config.py unless given (tests pass in their own)."""
        self.lights = lights if lights is not None else Lights()
        self.controls = controls if controls is not None else Controls()
        self.seats = geometry.SEATS

    @property
    def controllers(self):
        return self.controls.connected()


def load_game(name=None):
    """The Game class of the game called `name` (default config.GAME): the file games/NAME.py, or the folder
    games/NAME/ with the Game class in its game.py. A name with a dot in it ("mygames.chess") is imported as it is."""
    name = name or config.GAME
    path = name if "." in name else "games." + name
    mod = __import__(path, None, None, ["Game"])
    if not hasattr(mod, "Game"):
        mod = __import__(path + ".game", None, None, ["Game"])
    return mod.Game


class Host:
    """One game on one board. frame(now) is one pass of the loop; run() calls it config.FPS times a second."""

    def __init__(self, game_class=None, board=None):
        self.board = board if board is not None else Board()
        self.game = (game_class or load_game())(self.board)

    def frame(self, now):
        board = self.board
        game = self.game
        for kind, c in board.controls.take_notices():
            if kind == ADDED:
                game.controller_added(c, now)
            else:
                game.controller_removed(c, now)
        for c, a in board.controls.poll(now):
            game.event(c, a, now)
        game.update(now)
        lights = board.lights
        lights.fill(OFF)
        lights.now = now
        game.draw(lights, now)
        lights.show()


def run(game=None):
    """Run the game called `game` (default config.GAME) until power-off."""
    h = Host(load_game(game))
    period = 1.0 / config.FPS
    while True:
        now = time.monotonic()
        h.frame(now)
        left = period - (time.monotonic() - now)
        if left > 0:
            time.sleep(left)

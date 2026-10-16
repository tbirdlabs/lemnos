# The game host: runs one game on the board. It owns the lights and the controllers; the game owns everything else.
#
# A game is a module with a Game class:
#   Game(board)                  board.lights (leds.Lights), board.controls (controls.Controls),
#                                board.seats = 6
#   game.event(controller, action, now)   one action from one controller (controls.ACTIONS)
#   game.update(now)             called every frame: timers, animations, computer players
#   game.draw(lights, now)       draw the whole frame (every LED it wants lit); the host calls lights.show()
# Nothing in the host, leds.py or controls.py changes for a new game.

import time
import config
import leds
import controls


class Board:
    def __init__(self, lights, ctl):
        self.lights = lights
        self.controls = ctl
        self.seats = leds.SEATS


def run(game_name=None):
    lights = leds.Lights()
    ctl = controls.Controls()
    mod = __import__(game_name or config.GAME)
    game = mod.Game(Board(lights, ctl))
    frame = 1.0 / config.FPS
    while True:
        now = time.monotonic()
        for c, a in ctl.poll(now):
            game.event(c, a, now)
        game.update(now)
        lights.fill(leds.OFF)
        game.draw(lights, now)
        lights.show()
        left = frame - (time.monotonic() - now)
        if left > 0:
            time.sleep(left)

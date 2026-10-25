# Wired controller test: reads the pins in config.CONTROLLERS directly, without the host, the lobby or the hubs, so a
# controller that does nothing in a game can be checked on its own. From the REPL (Ctrl-C, then Enter):
#     from gamehost import ctltest; ctltest.main()
# or put that line in code.py in place of the host. Ctrl-C stops it.
#
# Each controller lights the bar it carries ("bar"; the first one carries bar 1 by default), or else its seat's bar
# (seat None = seat 1); it starts half full, in red.
#   encoder turned      clockwise adds a light, counterclockwise takes one off ("reverse" flips it)
#   button "pick"       next color          button "back"       color before
#   button "move"       adds a light        button "move_back"  takes one off
# Scan switches count as plain buttons here (no auto-scan). Everything is printed on the serial console: each
# switch's level at the start (a switch that reads pressed before anyone touches it is shorted or wired normally
# closed), every press and release, and every raw encoder count, so an encoder that counts but never reaches a
# detent (a wrong divisor) or doesn't count at all (A or B or its common not connected) shows up.

import time
import board
import digitalio
import rotaryio
import config
from . import geometry as G
from .controls import wired_bar
from .lights import Lights, OFF

COLORS = ((255, 0, 0), (255, 96, 0), (255, 255, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255), (160, 0, 255),
          (255, 255, 255))
NAMES = ("red", "orange", "yellow", "green", "cyan", "blue", "purple", "white")
EMPTY = (6, 6, 6)                        # the bar's unlit lights, dim, so it shows where the bar is
DEBOUNCE_S = 0.02


class Player:
    def __init__(self, k, spec):
        self.name = spec.get("name", "wired")
        self.seat = spec.get("seat") or 1
        self.bar = wired_bar(k, spec)
        self.lit = G.BAR_LEDS // 2
        self.color = 0

    def change(self, what, d):
        if what == "lit":
            self.lit = max(0, min(G.BAR_LEDS, self.lit + d))
            print("  %s (seat %d): %d lit" % (self.name, self.seat, self.lit))
        else:
            self.color = (self.color + d) % len(COLORS)
            print("  %s (seat %d): %s" % (self.name, self.seat, NAMES[self.color]))

    def draw(self, lights):
        colors = [COLORS[self.color] if i < self.lit else EMPTY for i in range(G.BAR_LEDS)]
        if self.bar:
            lights.bar_at(self.bar, colors)
        else:
            lights.bar(self.seat, colors)


DOES = {"pick": ("color", 1), "back": ("color", -1), "move": ("lit", 1), "move_back": ("lit", -1)}


class Switch:
    def __init__(self, player, spec):
        self.player = player
        self.pin = spec["pin"]
        self.does = "pick" if spec["type"] == "scan" else spec.get("does", "pick")
        self.io = digitalio.DigitalInOut(getattr(board, self.pin))
        self.io.switch_to_input(pull=digitalio.Pull.UP)
        self.down = not self.io.value
        self.changed = 0.0
        print("  %s %s (%s): %s" % (player.name, self.pin, self.does,
                                    "PRESSED at the start: shorted, or a normally-closed switch?" if self.down
                                    else "open"))

    def poll(self, now):
        down = not self.io.value
        if down != self.down and now - self.changed >= DEBOUNCE_S:
            self.down = down
            self.changed = now
            print("%s %s %s" % (self.player.name, self.pin, "pressed" if down else "released"))
            if down and self.does in DOES:
                self.player.change(*DOES[self.does])


class Knob:
    def __init__(self, player, spec):
        self.player = player
        self.pins = "%s/%s" % (spec["a"], spec["b"])
        self.divisor = spec.get("divisor", 4)
        self.sign = -1 if spec.get("reverse") else 1
        # Divisor 1: every quadrature count, so partial detents show too
        self.enc = rotaryio.IncrementalEncoder(getattr(board, spec["a"]), getattr(board, spec["b"]), divisor=1)
        self.raw = self.enc.position
        self.detent = 0
        print("  %s encoder %s: %d counts a detent%s" % (player.name, self.pins, self.divisor,
                                                         ", reversed" if self.sign < 0 else ""))

    def poll(self, now):
        raw = self.enc.position
        if raw == self.raw:
            return
        self.raw = raw
        detent = int(raw * self.sign / self.divisor)    # toward zero, like a detent half turned back
        print("%s encoder %s: count %d, detent %d" % (self.player.name, self.pins, raw, detent))
        while self.detent != detent:
            d = 1 if detent > self.detent else -1
            self.detent += d
            self.player.change("lit", d)


def main():
    print("Wired controller test (config.CONTROLLERS). Ctrl-C stops it.")
    players = []
    inputs = []
    for k, spec in enumerate(config.CONTROLLERS):
        p = Player(k, spec)
        players.append(p)
        print("%s, %s:" % (p.name, "bar %d" % p.bar if p.bar else "seat %d" % p.seat))
        for inp in spec["inputs"]:
            kind = inp.get("type")
            try:
                if kind == "encoder":
                    inputs.append(Knob(p, inp))
                elif kind in ("button", "scan"):
                    inputs.append(Switch(p, inp))
                else:
                    print("  %s input: not tested here" % kind)
            except Exception as e:                       # a wrong pin name, a pin already in use, ...
                print("  %s input NOT SET UP: %s: %s" % (kind, type(e).__name__, e))
    if not inputs:
        print("No wired inputs to test.")
    lights = Lights()
    while True:
        now = time.monotonic()
        for i in inputs:
            i.poll(now)
        lights.fill(OFF)
        for p in players:
            p.draw(lights)
        lights.show()
        time.sleep(0.005)

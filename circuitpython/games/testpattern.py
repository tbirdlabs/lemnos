# Test pattern: checks every LED, every color and every address. Set GAME = "testpattern" in config.py.
#
# Red fills the board one LED at a time, then green over it, then blue, and around again. The order is by place, not
# by strip: rows A to G (farthest from seat 1 first), each left to right as seen from seat 1 (the line LEDs too, on
# the small board), then each bar, 1 to 6 as in BARS_AT, LED 1 to 10 (left to right as its player sees it). So a
# light that comes on out of turn is mapped wrong (a row running backward, a swapped channel), one that stays dark
# or the wrong color in a fill is a dead LED or color, and the board full of each color in turn shows all three.
#
# Controls: pick pauses (and goes on); while paused, move / move back step one LED and the serial console prints
# which LED it is and where it is on the strip. Back starts over from dark.
#
# Unlike a game, this reads the LED map (gamehost/lights.py) so it can print strip addresses.

from gamehost import geometry as G
from gamehost import lights as L
from gamehost.game import Game as BaseGame

OFF = (0, 0, 0)
COLORS = ((255, 0, 0), (0, 255, 0), (0, 0, 255))
NAMES = ("red", "green", "blue")
STEP_S = 0.05                            # seconds per LED (20 a second)
HOLD_S = 1.0                             # the board full of one color, before the next starts
WHICH = ("left", "middle", "right")


def card(lights, now):
    """The board's game picker shows this (gamehost/lobby.py): each row in turn red, green and blue."""
    for r, row in enumerate(G.ROWS):
        for t in row:
            lights.spot(t, [COLORS[r % 3]] * 3)


def sequence():
    """Every LED, by lights.py's logical number, in the order the pattern lights them."""
    seq = []
    for r, row in enumerate(G.ROWS):
        for c, t in enumerate(row):
            if L.LINES:
                seq.append(L.FIRST_LINE + G.LINE_START[r] + c)
            seq += [t * G.LEDS_PER_SPOT + i for i in range(G.LEDS_PER_SPOT)]
        if L.LINES:
            seq.append(L.FIRST_LINE + G.LINE_START[r] + len(row))
    for s in range(G.SEATS):
        seq += [L.ISLAND + s * G.BAR_LEDS + i for i in range(G.BAR_LEDS)]
    return seq


def describe(k):
    """Logical LED k by name, and where it is on the strip."""
    if k < L.ISLAND:
        t, i = divmod(k, G.LEDS_PER_SPOT)
        what = "hex %s, %s light" % (G.name(t), WHICH[i])
    elif k < L.FIRST_LINE:
        s, i = divmod(k - L.ISLAND, G.BAR_LEDS)
        what = "bar %d, LED %d" % (s + 1, i + 1)
    else:
        what = "line %s" % G.line_name(k - L.FIRST_LINE)
    p = L.PHYS[k]
    return "%s (channel %d, LED %d from 0)" % (what, p // L.STRAND, p % L.STRAND)


class Game(BaseGame):
    def __init__(self, board):
        BaseGame.__init__(self, board)
        self.seq = sequence()
        self.slot = [0] * L.COUNT                # each LED's place in the sequence
        for n, k in enumerate(self.seq):
            self.slot[k] = n
        self.restart(0.0)
        print("Test pattern: %d LEDs. pick = pause, move / move back = step (paused), back = start over"
              % len(self.seq))

    def restart(self, now):
        self.color = 0                           # the color filling now
        self.under = OFF                         # what it fills over
        self.done = 0                            # LEDs lit in this color so far
        self.next = now + STEP_S
        self.paused = False

    def step(self, now):
        """One LED forward; after the last, hold, then the next color."""
        if self.done < len(self.seq):
            self.done += 1
            self.next = now + (HOLD_S if self.done == len(self.seq) else STEP_S)
        else:
            self.under = COLORS[self.color]
            self.color = (self.color + 1) % len(COLORS)
            self.done = 0
            self.next = now + STEP_S

    def report(self):
        if self.done:
            print("%-5s %3d of %d: %s" % (NAMES[self.color], self.done, len(self.seq), describe(self.seq[self.done - 1])))
        else:
            print("%-5s start" % NAMES[self.color])

    def event(self, controller, action, now):
        if action == "pick":
            self.paused = not self.paused
            self.next = now + STEP_S
            if self.paused:
                self.report()
        elif action in ("move", "move_back") and self.paused:    # ignored while running (a scan switch sends move)
            if action == "move":
                self.step(now)
            else:
                self.done = max(0, self.done - 1)
            self.report()
        elif action == "back":
            self.restart(now)

    def update(self, now):
        if not self.paused and now >= self.next:     # at most one LED a frame
            self.step(now)

    def draw(self, lights, now):
        col = [COLORS[self.color] if self.slot[k] < self.done else self.under for k in range(L.COUNT)]
        for t in range(G.SPOTS):
            lights.spot(t, col[t * G.LEDS_PER_SPOT:(t + 1) * G.LEDS_PER_SPOT])
        for s in range(G.SEATS):
            b = L.ISLAND + s * G.BAR_LEDS
            lights.bar_at(s + 1, col[b:b + G.BAR_LEDS])     # bar by place (BARS_AT), not by who sits there
        for k in range(L.LINES):
            lights.line(k, col[L.FIRST_LINE + k])

# Clock: the board as an analog wall clock, for when nobody's playing. Set GAME = "clock" in config.py.
#
# The island is the face, as round as 37 hexes get: the six corner hexes stay dark. Three hands turn smoothly from
# the center hex, each one LED wide and each a primary color: the hour hand (blue, to the second ring of hexes),
# the minute hand (green, to the edge) and the second hand (red, to the edge). Where they cross, their light adds:
# hour and minute make cyan, minute and second yellow, hour and second magenta, all three white. The island's LEDs
# sit in 7 evenly spaced rows, so a hand lights, in each row it crosses, the LEDs nearest its line there: one where
# it's steep, a run along the row where it's nearly level.
# The six bars around the island make a ring of 60 lights, one a minute, running clockwise from 12 o'clock at the
# middle of the top bar: a pair of dim lights marks each hour (brighter at 12, 3, 6 and 9), the minute shows in the
# minute hand's color, and a red light follows the second hand round.
#
# The time comes from an RTC chip on the I2C bus if config.RTC names one, else from the board's own clock
# (gamehost/walltime.py). Until it's set, the hour marks breathe. To set it, type on the serial console
#     time 14:32        (or time 2:32pm, time 14:32:05, time 2026-10-20 14:32:05)
# and Enter; "time" alone says what it is. tools/settime.ps1 sends the computer's time. Setting it sets the chip too,
# which keeps it through power-off.
#
# Controls: pick turns the seconds (the hand and its light on the ring) off and on.

import math
from gamehost import geometry as G
from gamehost import walltime
from gamehost.game import Game as BaseGame

OFF = (0, 0, 0)
FACE = (6, 8, 24)                        # the round face, dim
HUB = (110, 90, 60)                      # the center hex, where the hands meet
HOUR = (0, 0, 255)                       # the hour hand
MINUTE = (0, 255, 0)                     # the minute hand, and the minute on the ring
SECOND = (255, 0, 0)                     # the second hand, and its light on the ring
MARK = (30, 30, 30)                      # each of the two lights either side of an hour on the ring
MARK_BIG = (90, 90, 90)                  # 12, 3, 6 and 9
HOUR_LEN = 2.0                           # hand lengths in hex widths from the center (the face's edge is 2.65 out)
MINUTE_LEN = 2.75
SECOND_LEN = 2.75
BREATHE_MS = 3000                        # the hour marks breathing, while the time isn't set
FACE_RADIUS = 2.8                        # hexes centered nearer than this are the face (not the 6 corners, at 3)
RING = 60
CW_SEATS = (4, 5, 6, 1, 2, 3)            # the bars clockwise from the top
SQRT3_2 = math.sqrt(3) / 2
ROW_GAP = SQRT3_2                        # rows of hexes (and LEDs) are this far apart, in hex widths


def card(lights, now):
    """The board's game picker shows this (gamehost/lobby.py): the face at ten past ten."""
    for t in range(G.SPOTS):
        if max(abs(G.Q[t]), abs(G.R[t]), abs(G.Q[t] + G.R[t])) < 3:
            lights.spot(t, [FACE] * 3)
    lights.spot(G.CENTER, [HUB] * 3)
    lights.spot("C3", [HOUR] * 3)
    for t in ("C4", "B4"):
        lights.spot(t, [MINUTE] * 3)


def ring_at(j):
    """Ring light j (0-59, clockwise from 12 o'clock; j covers minute j to j+1) as (seat, bar light 0-9).
    A bar's light 0 is at its player's left, so along every bar the lights count anticlockwise."""
    k = (j + 5) % RING
    return CW_SEATS[k // 10], 9 - k % 10


RING_AT = tuple(ring_at(j) for j in range(RING))
SEAT_RING = [None] + [[RING_AT.index((s, i)) for i in range(G.BAR_LEDS)] for s in range(1, G.SEATS + 1)]


def positions(has_lines):
    """Where the island's LEDs are, in hex widths from the center (x to the right, y down, as seen from seat 1):
    (for each spot its 3 LEDs' (x, y), for each line its LED's (x, y), empty on the large board).
    A hex's 3 LEDs are a third of a hex apart on the large board, a quarter on the small (where the line LEDs sit
    on the edges between them), so along a row the LEDs are evenly spaced."""
    step = 0.25 if has_lines else 1.0 / 3
    spots = []
    for t in range(G.SPOTS):
        x = G.Q[t] + G.R[t] / 2
        y = G.R[t] * SQRT3_2
        spots.append(tuple((x + (i - 1) * step, y) for i in range(3)))
    lines = []
    if has_lines:
        for k in range(G.LINES):
            r = G.LINE_ROW[k]
            first = G.ROWS[r][0]
            lines.append((G.Q[first] + G.R[first] / 2 - 0.5 + G.LINE_COL[k], (r - G.RADIUS) * SQRT3_2))
    return spots, lines


def mix(base, parts):
    """base plus each (color, amount), clamped."""
    r, g, b = base
    for c, k in parts:
        r += c[0] * k
        g += c[1] * k
        b += c[2] * k
    return (min(255, int(r)), min(255, int(g)), min(255, int(b)))


def marks(k):
    """The ring with only the hour marks, at brightness k."""
    out = [OFF] * RING
    for h in range(12):
        c = MARK_BIG if h % 3 == 0 else MARK
        c = (int(c[0] * k), int(c[1] * k), int(c[2] * k))
        out[5 * h - 1] = c
        out[5 * h] = c
    return out


MARKS = marks(1.0)


class Row:
    """One row of the island's LEDs, left to right: y, the first one's x, the spacing, and each LED as
    (the color list it's in, its place there)."""

    def __init__(self, y, leds):
        leds.sort(key=lambda e: e[0])
        self.y = y
        self.x0 = leds[0][0]
        self.step = (leds[-1][0] - leds[0][0]) / (len(leds) - 1)
        self.leds = [(where, i) for x, where, i in leds]


class Game(BaseGame):
    def __init__(self, board):
        BaseGame.__init__(self, board)
        self.wall = walltime.Wall()
        self.seconds = True
        spots_at, lines_at = positions(board.lights.has_lines)
        face = [G.Q[t] ** 2 + G.Q[t] * G.R[t] + G.R[t] ** 2 < FACE_RADIUS ** 2 for t in range(G.SPOTS)]
        self.spot_colors = [[FACE if face[t] else OFF] * 3 for t in range(G.SPOTS)]
        self.spot_colors[G.CENTER] = [HUB] * 3
        self.line_colors = [FACE if all(face[t] for t in G.line_spots(k)) else OFF for k in range(len(lines_at))]
        self.spot_base = [list(c) for c in self.spot_colors]
        self.line_base = list(self.line_colors)
        rows = [[] for _ in G.ROW_LENGTHS]
        for t in range(G.SPOTS):
            for i, (x, y) in enumerate(spots_at[t]):
                rows[G.ROW[t]].append((x, t, i))
        for k, (x, y) in enumerate(lines_at):
            rows[G.LINE_ROW[k]].append((x, -1, k))          # -1: a line LED
        self.rows = [Row((r - G.RADIUS) * ROW_GAP, rows[r]) for r in range(len(rows))]
        self.lit = []                    # the hands' LEDs as drawn: (spot or -1, place)

    def event(self, controller, action, now):
        if action == "pick":
            self.seconds = not self.seconds

    HELP = (("time", "the time, and where it came from"),
            ("time 14:32", "set it; also 2:32pm, 14:32:05, 2026-10-20 14:32:05"))

    def command(self, text, now):
        return self.wall.command(text)

    def update(self, now):
        self.wall.update()

    def hand(self, turn, length):
        """The LEDs a hand lights, pointing `turn` of the way round from 12 o'clock (0..1), `length` long: in each
        row it crosses, those nearest its line (the LEDs within half a spacing of where it runs in that row)."""
        a = 2 * math.pi * turn
        ux = math.sin(a)
        uy = -math.cos(a)
        out = []
        half = ROW_GAP / 2
        for row in self.rows:
            # how far along the hand it's in this row's band (y within half a row gap)
            if -1e-9 < uy < 1e-9:
                if abs(row.y) > half:
                    continue
                t0, t1 = 0.0, length
            else:
                t0 = (row.y - half) / uy
                t1 = (row.y + half) / uy
                if t0 > t1:
                    t0, t1 = t1, t0
                t0 = max(t0, 0.0)
                t1 = min(t1, length)
                if t0 > t1:
                    continue
            s = row.step
            if abs(ux) * ROW_GAP < s * abs(uy):
                # steep: crosses less than an LED spacing within the band, so just the LED nearest where it
                # crosses the row's middle (or comes nearest it, at the tip)
                tc = min(max(row.y / uy, t0), t1)
                xa = xb = tc * ux
            else:                        # nearly level: every LED along its way through the band
                xa = t0 * ux
                xb = t1 * ux
                if xa > xb:
                    xa, xb = xb, xa
            lo = max(0, int(math.floor((xa - row.x0) / s + 0.5)))
            hi = min(len(row.leds) - 1, int(math.floor((xb - row.x0) / s + 0.5)))
            for k in range(lo, hi + 1):
                out.append(row.leds[k])
        return out

    def draw_hands(self, ms):
        """Put the hands on the island's lights at ms past midnight (all three turn smoothly)."""
        for t, i in self.lit:            # back to the face
            if t < 0:
                self.line_colors[i] = self.line_base[i]
            else:
                self.spot_colors[t][i] = self.spot_base[t][i]
        self.lit = []
        hands = [(ms % 43200000 / 43200000.0, HOUR_LEN, HOUR), (ms % 3600000 / 3600000.0, MINUTE_LEN, MINUTE)]
        if self.seconds:
            hands.append((ms % 60000 / 60000.0, SECOND_LEN, SECOND))
        on = {}                          # (spot or -1, place): the hands there, mixed
        for turn, length, color in hands:
            for led in self.hand(turn, length):
                if led[0] != G.CENTER:
                    c = on.get(led, OFF)
                    on[led] = (min(255, c[0] + color[0]), min(255, c[1] + color[1]), min(255, c[2] + color[2]))
        for (t, i), c in on.items():
            if t < 0:
                self.line_colors[i] = c
            else:
                self.spot_colors[t][i] = c
            self.lit.append((t, i))

    def ring(self, ms):
        """The 60 ring lights' colors."""
        if self.wall.known:
            out = list(MARKS)
        else:                            # not set: the marks breathe
            phase = ms % BREATHE_MS / BREATHE_MS
            out = marks(0.15 + 0.85 * abs(phase * 2 - 1))

        def point(pos, c):               # a light at pos (in minutes round the ring), shared by the two nearest
            x = pos - 0.5
            j = int(math.floor(x))
            f = x - j
            for jj, k in ((j % RING, 1 - f), ((j + 1) % RING, f)):
                out[jj] = mix(out[jj], ((c, k),))

        point(ms % 3600000 / 60000.0, MINUTE)
        if self.seconds:
            point(ms % 60000 / 1000.0, SECOND)
        return out

    def draw(self, lights, now):
        ms = self.wall.ms()
        self.draw_hands(ms)
        for t in range(G.SPOTS):
            lights.spot(t, self.spot_colors[t])
        for k in range(len(self.line_colors)):
            lights.line(k, self.line_colors[k])
        ring = self.ring(ms)
        for seat in range(1, G.SEATS + 1):          # by place: each bar where it is, whoever holds it
            lights.bar_at(seat, [ring[j] for j in SEAT_RING[seat]])

# Rain: showers on a pond, for when nobody's playing (an attract screen, or a wall decoration).
# Set GAME = "rain" in config.py, or pick it in the game picker.
#
# The island is a pond. Each raindrop lands in the middle of a hex and sends a ring rippling outward across every LED
# by its real distance (geometry.led_places, the line LEDs too on the small board), fading as it spreads; where rings
# cross, their light adds. A shower builds and passes: a few first drops (where it starts); rain building to a
# downpour of rings over rings; easing off to the last drop; the pond still, a drip now and then; and the next. A
# drop's splash swells over a fifth of a second, so nothing flashes.
#
# Every bar shows how hard it's raining, in blue. Controls: pick drops a pebble: a bigger splash, somewhere, with a
# second, fainter ring trailing the first.
#
# Fast on purpose (games/aurora.py has the story): whole numbers and tables only. Distances are in 16ths of a hex
# width; for each hex the LEDs are sorted by distance from it once, at the start, so a ring of radius r only touches
# the LEDs at that distance (a slice of the list, found by a binary search), never all of them; and each LED's color
# comes from a table, so working out a frame makes no new colors. Small, too: the board also has the game picker and
# whatever else loaded, so it keeps only the sorted lists (about 12 KB), not the LEDs' places or anything to speed
# up the search.

import random
from gamehost import geometry as G
from gamehost.game import Game as BaseGame

OFF = (0, 0, 0)
POND = (0, 10, 32)                       # the still pond: dark blue, but enough to see at low brightness
RIPPLE = (140, 190, 255)                 # a ring at its brightest
BAR = (20, 70, 255)
UNIT = 16                                # distances in 16ths of a hex width
SPEED = 1.5                              # how fast a ring spreads, hex widths a second
LIFE = 2.6                               # seconds a ring lasts, fading all the way
RISE = 0.2                               # seconds a splash takes to swell (so nothing flashes)
WIDTH = 7                                # a ring's half width, 16ths of a hex
TRAIL = 9                                # a pebble's second ring, this far behind the first (16ths), at TRAIL_AMP
TRAIL_AMP = 0.45
DROP = 0.5                               # a drop's ring at its brightest, of full (so rings that cross don't all add
                                         # up to a white blob in a downpour)
PEBBLE = 1.0                             # a pebble's: bigger, and its ring lasts longer
MOST = 12                                # rings at once, at most (each costs the RP2040 about 1-2 ms an update)
LEVELS = 64                              # color steps between the still pond and a full ring
STEP = 12                                # an LED moves at most this many levels an update: dark to full in a quarter
                                         # of a second at the quickest, however many rings cross it at once (in a
                                         # downpour, several passing one LED in the same moment can add up to a jump)
STILL_S = (20, 45)                       # each part of a shower, seconds (at random, between these)
BUILD_S = (30, 60)
POUR_S = (30, 80)
EASE_S = (40, 80)
PEAK = (1.5, 4.0)                        # drops a second at a shower's height (at random, between these)
DRIP = 0.03                              # drops a second in a still pond (from the trees)
DRAW_HZ = 20                             # the pond is worked out this often (frames between reuse it)


def at_least(ds, b):
    """The first place in the sorted distances ds that is b or more (len(ds) if none is)."""
    lo, hi = 0, len(ds)
    while lo < hi:
        mid = (lo + hi) >> 1
        if ds[mid] < b:
            lo = mid + 1
        else:
            hi = mid
    return lo


def smooth(x):
    x = 0.0 if x < 0 else 1.0 if x > 1 else x
    return x * x * (3 - 2 * x)


def _profile():
    """A ring's brightness across its width, 0-255, for distances -WIDTH..WIDTH from its crest: a rounded crest,
    (1 - x^2)^2, flat on top. (A peaked one changed fastest right at the crest, and in a downpour, crests passing an
    LED together added up to a near-flash.)"""
    out = bytearray(2 * WIDTH + 1)
    for i in range(2 * WIDTH + 1):
        x = (i - WIDTH) / (WIDTH + 1)
        out[i] = min(255, int(256 * (1 - x * x) * (1 - x * x)))
    return out


PROFILE = _profile()
COLORS = tuple((POND[0] + (RIPPLE[0] - POND[0]) * i // (LEVELS - 1), POND[1] + (RIPPLE[1] - POND[1]) * i // (LEVELS - 1),
                POND[2] + (RIPPLE[2] - POND[2]) * i // (LEVELS - 1)) for i in range(LEVELS))


class Pond:
    """The pond and its rings, and how hard it's raining. `part`: still, build, pour, ease."""

    def __init__(self, has_lines=False, rng=random):
        self.rng = rng
        leds = G.led_places(has_lines)    # (only to build the lists: they're in this order, spots then lines)
        n = len(leds)
        self.n = n
        # For each hex: the LEDs sorted by distance from its middle, their numbers and their distances (16ths)
        self.order, self.dist = [], []
        for t in range(G.SPOTS):
            cx, cy = G.Q[t] + G.R[t] / 2, G.R[t] * G.SQRT3_2
            d = [int(((p[2] - cx) ** 2 + (p[3] - cy) ** 2) ** 0.5 * UNIT + 0.5) for p in leds]
            ks = sorted(range(n), key=lambda k: d[k])
            self.order.append(bytes(ks))
            self.dist.append(bytes([d[k] for k in ks]))
        leds = None
        self.rings = []                    # [hex, when it landed, strength 0-1, how long it lasts, a second ring?]
        self.level = [0] * n               # working list, reused: each LED's brightness, 256ths of a level
        self.zero = [0] * n
        self.shown = [0] * n               # each LED's level as last shown (STEP: how far it may move from it)
        self.rate = 0.0                    # drops a second now
        self.peak = PEAK[0]
        self.drops = 0
        self.to("build", 0.0)              # a shower on its way from the start: a still pond looks like nothing

    def pick(self, span):
        return span[0] + self.rng.random() * (span[1] - span[0])

    def to(self, part, now):
        self.part = part
        self.since = now
        self.lasts = self.pick({"still": STILL_S, "build": BUILD_S, "pour": POUR_S, "ease": EASE_S}[part])
        if part == "build":
            self.peak = self.pick(PEAK)

    def drop(self, now, strength=DROP, life=LIFE, trail=False):
        if len(self.rings) < MOST:
            self.rings.append([int(self.rng.random() * G.SPOTS), now, strength, life, trail])
            self.drops += 1

    def run(self, now, dt):
        f = min(1.0, (now - self.since) / self.lasts)
        if self.part == "still":
            self.rate = DRIP
            nxt = "build"
        elif self.part == "build":
            self.rate = DRIP + (self.peak - DRIP) * smooth(f)
            nxt = "pour"
        elif self.part == "pour":
            self.rate = self.peak
            nxt = "ease"
        else:
            self.rate = DRIP + (self.peak - DRIP) * (1 - smooth(f))
            nxt = "still"
        if f >= 1:
            self.to(nxt, now)
        if self.rng.random() < self.rate * dt:
            self.drop(now)
        self.rings = [r for r in self.rings if now - r[1] < r[3]]

    def colors(self, now):
        """Each LED's color (in geometry.led_places order)."""
        level = self.level
        level[:] = self.zero
        profile, top = PROFILE, LEVELS - 1
        speed = SPEED * UNIT
        for t, at, strength, life, trail in self.rings:
            age = now - at
            if age < 0:
                continue
            fade = (1 - age / life) * strength * (age / RISE if age < RISE else 1.0)
            amp = int(fade * top)          # this ring's crest, in levels
            if amp <= 0:
                continue
            r = int(age * speed)
            order, dist = self.order[t], self.dist[t]
            for crest, a in ((r, amp), (r - TRAIL, int(amp * TRAIL_AMP))) if trail else ((r, amp),):
                if crest + WIDTH < 0 or a <= 0:
                    continue
                lo = at_least(dist, crest - WIDTH)
                hi = at_least(dist, crest + WIDTH + 1)
                for i in range(lo, hi):
                    level[order[i]] += a * profile[dist[i] - crest + WIDTH]
        colors, shown = COLORS, self.shown
        out = [None] * len(level)
        for k in range(len(level)):
            v = level[k] >> 8
            if v > top:
                v = top
            was = shown[k]
            if v > was + STEP:
                v = was + STEP
            elif v < was - STEP:
                v = was - STEP
            shown[k] = v
            out[k] = colors[v]
        return out

    def strength(self):
        """0-1: how hard it's raining."""
        return min(1.0, self.rate / PEAK[1])


def card(lights, now):
    """The board's game picker shows this (gamehost/lobby.py): the pond, with a drop's ring around the middle and a
    fainter one inside it. (No bright middle: that looks like the picker's own blinking white hex.)"""
    for t in range(G.SPOTS):
        ring = max(abs(G.Q[t]), abs(G.R[t]), abs(G.Q[t] + G.R[t]))
        c = COLORS[(0, LEVELS // 3, LEVELS - 1, 0)[ring]]
        lights.spot(t, [c] * 3)


class Game(BaseGame):
    def __init__(self, board):
        BaseGame.__init__(self, board)
        self.pond = Pond(board.lights.has_lines)
        self.last = None
        self.drawn = None                 # (when, the colors) last worked out
        self.pebble = -9.0

    def event(self, controller, action, now):
        if action == "pick" and now - self.pebble >= 0.5:
            self.pebble = now
            self.pond.drop(now, PEBBLE, LIFE * 1.4, True)

    def update(self, now):
        if self.last is None:
            self.pond.since = now         # (the still pond starts when the game does)
        else:
            self.pond.run(now, min(0.1, now - self.last))
        self.last = now

    def draw(self, lights, now):
        if self.drawn is None or now - self.drawn[0] >= 1.0 / DRAW_HZ or now < self.drawn[0]:
            self.drawn = (now, self.pond.colors(now))
        colors = self.drawn[1]
        per, spots = G.LEDS_PER_SPOT, G.SPOTS * G.LEDS_PER_SPOT
        for t in range(G.SPOTS):            # (geometry.led_places order: each spot's LEDs, then the lines)
            lights.spot(t, colors[t * per:t * per + per])
        for k in range(len(colors) - spots):
            lights.line(k, colors[spots + k])
        n = int(self.pond.strength() * G.BAR_LEDS + 0.5)
        bar = [BAR if i < n else OFF for i in range(G.BAR_LEDS)]
        for seat in range(1, G.SEATS + 1):
            lights.bar(seat, bar)

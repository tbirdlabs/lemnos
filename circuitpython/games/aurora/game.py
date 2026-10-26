# Aurora: the northern lights over the island, for when nobody's playing (an attract screen, or a wall decoration).
# Set GAME = "aurora" in config.py, or pick it in the game picker.
#
# The island is a patch of sky, as on a wall: row A at the top, row G nearest the horizon. Each curtain of light has
# a bright lower edge swaying along a slow wavy line, and fades upward into the dark; rays drift along it. Its color
# goes by height, as a real aurora's does: green at the edge, teal above, violet high up. A display builds and
# passes: a quiet sky with a faint glow low down; then more curtains, brighter, higher in the sky and swaying faster;
# a peak, sometimes with a surge (the curtains leap, ripple quicker, and their edges turn pink); then a long fade, and
# quiet again before the next. Nothing flashes: every change is a slow drift.
#
# Every bar shows how active the sky is (aurora watchers' 0-9 scale, the Kp index), green to violet to pink.
# Controls: pick sets off a surge (and starts a display, in a quiet sky).
#
# Each LED's place on the board (geometry.led_places) is all it needs, so it draws the same on both boards.
#
# Working it out is all whole numbers and tables: the RP2040 has no hardware floats, so float math is done in
# software and is slow, and anything done 155 times a frame adds up. (On the small board, a float version took
# 50-70 ms a sky; one built on ulab's float arrays also made a new array for every step, and the memory clean-ups
# after them stalled the board for up to 400 ms.) Places are in 64ths of a hex width; a wave is a lookup in a
# 1024-step sine table, once per column of LEDs; each curtain's fade, already colored, is a table by distance from
# its edge; so for each LED it's a subtraction, three lookups and three additions. The working lists are kept and
# reused, so working out the sky leaves little memory to clean up.

import math
import random
from gamehost import geometry as G
from gamehost.game import Game as BaseGame

OFF = (0, 0, 0)
EDGE = (30, 255, 80)                     # a curtain's lower edge
MIDDLE = (0, 170, 150)                   # higher up
HIGH = (110, 40, 210)                    # the top of a curtain
SURGE_EDGE = (255, 50, 140)              # the edge in a surge
CURTAINS = 3
QUIET_S = (40, 90)                       # each part of a display, seconds (at random, between these)
BUILD_S = (60, 120)
PEAK_S = (40, 90)
FADE_S = (90, 160)
PEAK = (0.45, 1.0)                       # how strong a display gets
QUIET = 0.07                             # the sky between displays
SURGE_S = 25.0                           # a surge dies away over this long
SWELL_S = 3.0                            # and swells over this long, first
SURGE_CHANCE = 0.5                       # a display's peak has a surge
DRAW_HZ = 10                             # the sky is worked out this often (frames between reuse it)
UNIT = 64                                # places in 64ths of a hex width
SINE = [int(round(1024 * math.sin(6.283185 * i / 1024))) for i in range(1024)]   # a turn in 1024 steps, +-1024
STEP = 1024 / 6.283185                   # sine table steps a radian
KP = ((30, 255, 80), (30, 255, 80), (30, 255, 80), (30, 255, 80), (0, 200, 140), (0, 170, 170), (80, 60, 220),
      (110, 40, 210), (200, 50, 180), (255, 50, 140))   # the bars, light by light


def smooth(x):
    x = 0.0 if x < 0 else 1.0 if x > 1 else x
    return x * x * (3 - 2 * x)


class Wave:
    """sin(k x + phase + how far it has run), at each column of LEDs: +-1024."""

    def __init__(self, xs, k, w, phase):
        self.steps = [int(k * x * STEP) for x in xs]       # each column's place in the turn, in table steps
        self.w = w
        self.t = phase                    # where it has run to (its phase, plus w x time with speed-ups), radians

    def advance(self, dt, speed):
        self.t += self.w * dt * speed

    def now(self):
        """Where it has run to, in sine table steps: its value at column j is SINE[(steps[j] + now()) & 1023]."""
        return int(self.t * STEP)


def mix(a, b, f):
    return [a[i] + (b[i] - a[i]) * f for i in range(3)]


class Curtain:
    def __init__(self, xs, rng, n):
        r = rng.random
        self.n = n                        # 0 is the first to show, the others join as the display grows
        self.shift = (r() - 0.5) * 0.8    # its edge, up or down from the others
        self.a1, self.a2 = 0.5 + 0.4 * r(), 0.15 + 0.15 * r()      # deep waves, so the edge cuts across rows
        self.w1 = Wave(xs, 0.6 + 0.6 * r(), (0.06 + 0.06 * r()) * (1 if r() < 0.5 else -1), 6.28 * r())
        self.w2 = Wave(xs, 1.2 + 0.8 * r(), (0.10 + 0.10 * r()) * (1 if r() < 0.5 else -1), 6.28 * r())
        self.rays = Wave(xs, 3.0 + 4.0 * r(), (0.2 + 0.3 * r()) * (1 if r() < 0.5 else -1), 6.28 * r())
        self.height = 2.5 + 1.5 * r()     # how far up it fades, in hex widths
        # Its fade above the edge, colored: by distance up (64ths), the color at full brightness times the fade
        # (1 - u)^2, green at the edge to teal halfway up to violet at the top
        top = int(self.height * UNIT)
        self.top = top
        self.up = [bytearray(top), bytearray(top), bytearray(top)]
        for d in range(top):
            u = d / top
            c = mix(EDGE, MIDDLE, u * 2) if u < 0.5 else mix(MIDDLE, HIGH, u * 2 - 1)
            f = (1 - u) * (1 - u)
            for i in range(3):
                self.up[i][d] = int(c[i] * f)

    def advance(self, dt, speed):
        for w in (self.w1, self.w2, self.rays):
            w.advance(dt, speed)


class Sky:
    """The aurora: its curtains and how active it is. `part`: quiet, build, peak, fade."""

    def __init__(self, has_lines=False, rng=random):
        self.rng = rng
        leds = G.led_places(has_lines)    # (only to build the lists below: they're in this order, spots then lines;
        xs = sorted(set(round(p[2], 4) for p in leds))      # not kept, it's 5 KB)
        self.xs = xs
        self.col = [xs.index(round(p[2], 4)) for p in leds]
        self.ys = [int(round(p[3] * UNIT)) for p in leds]
        n = len(leds)
        leds = None
        # working lists, kept and reused: making them afresh each time leaves memory to clean up, a long pause
        self.rs, self.gs, self.bs, self.zero = [0] * n, [0] * n, [0] * n, [0] * n
        self.edge, self.ray = [0] * len(xs), [0] * len(xs)
        self.curtains = [Curtain(xs, rng, i) for i in range(CURTAINS)]
        self.fringe_key = None            # the surge the fringe table (below every edge) was made for
        self.level = QUIET
        self.surge = 0.0
        self.swelling = False
        self.peak = PEAK[0]
        self.display(0.0, quiet=True)

    def pick(self, span):
        return span[0] + self.rng.random() * (span[1] - span[0])

    def display(self, now, quiet=False):
        """A new display, from its quiet sky (or straight into its build). The curtains that aren't showing are new
        ones; the first, which glows even in a quiet sky, carries on, so nothing jumps."""
        for i in range(1, CURTAINS):
            self.curtains[i] = Curtain(self.xs, self.rng, i)
        self.peak = self.pick(PEAK)
        self.surges = self.rng.random() < SURGE_CHANCE
        self.to("quiet" if quiet else "build", now)

    def to(self, part, now):
        self.part = part
        self.since = now
        self.lasts = self.pick({"quiet": QUIET_S, "build": BUILD_S, "peak": PEAK_S, "fade": FADE_S}[part])
        self.start = self.level           # where the level was when this part began
        if part == "peak" and self.surges:
            self.surge_at = now + self.rng.random() * self.lasts * 0.7
        else:
            self.surge_at = None

    def kick(self, now):
        """A surge now (pick); in a quiet sky, a display starts too."""
        self.swelling = True
        if self.part == "quiet":
            self.to("build", now)

    def run(self, now, dt):
        s = now - self.since
        f = min(1.0, s / self.lasts)
        if self.part == "quiet":
            self.level = self.start + (QUIET - self.start) * smooth(f)
            if f >= 1:
                self.display(now)
        elif self.part == "build":
            self.level = self.start + (self.peak - self.start) * smooth(f)
            if f >= 1:
                self.to("peak", now)
        elif self.part == "peak":
            self.level = self.peak
            if self.surge_at is not None and now >= self.surge_at:
                self.surge_at = None
                self.swelling = True
            if f >= 1:
                self.to("fade", now)
        else:
            self.level = self.start + (QUIET - self.start) * smooth(f)
            if f >= 1:
                self.to("quiet", now)
        if self.swelling:
            self.surge = min(1.0, self.surge + dt / SWELL_S)
            self.swelling = self.surge < 1.0
        else:
            self.surge = max(0.0, self.surge - dt / SURGE_S)
        speed = 0.5 + 1.0 * self.level + 1.5 * self.surge
        for c in self.curtains:
            c.advance(dt, speed)

    def activity(self):
        """0-1: how active the sky is, a surge included."""
        return min(1.0, self.level + 0.35 * self.surge)

    def fringe(self):
        """The table below every curtain's edge, by distance down (64ths): green at the edge, toward pink in a surge,
        times its sharp falloff. Made again only when the surge has changed (in 32nds)."""
        key = int(self.surge * 32)
        if key != self.fringe_key:
            surge = key / 32
            depth = int((0.3 + 0.35 * surge) * UNIT)
            pink = mix(EDGE, SURGE_EDGE, surge)
            self.down = [bytearray(depth), bytearray(depth), bytearray(depth)]
            for d in range(depth):
                v = d / depth
                c = mix(EDGE, pink, v)
                f = (1 - v) * (1 - v)
                for i in range(3):
                    self.down[i][d] = int(c[i] * f)
            self.fringe_key = key
        return self.down

    def colors(self):
        """Each LED's color (in geometry.led_places order)."""
        a = self.activity()
        surge = self.surge
        n = len(self.ys)
        ys, cols, ncol = self.ys, self.col, len(self.xs)
        rs, gs, bs, edge, ray = self.rs, self.gs, self.bs, self.edge, self.ray
        rs[:] = self.zero
        gs[:] = self.zero
        bs[:] = self.zero
        sine = SINE
        dr, dg, db = self.fringe()
        depth = len(dr)
        for c in self.curtains:
            weight = smooth(a * CURTAINS * 1.2 - c.n)      # the first curtain shows from a quiet sky, the rest as it grows
            if c.n == 0:
                weight = max(0.6, weight)
            if weight <= 0:
                continue
            # the edge sits low (near the horizon, row G) in a quiet sky and rises as the display grows
            base = int((2.3 - 2.0 * a + c.shift - 0.5 * surge) * UNIT)
            a1, a2 = int(c.a1 * UNIT), int(c.a2 * UNIT)
            s1, s2, sr = c.w1.steps, c.w2.steps, c.rays.steps
            t1, t2, tr = c.w1.now(), c.w2.now(), c.rays.now()
            bright = weight * (0.15 + 0.85 * a)
            r0, r1 = int(0.65 * 256 * bright), int(0.35 * 256 * bright)
            for j in range(ncol):
                edge[j] = base + ((a1 * sine[(s1[j] + t1) & 1023] + a2 * sine[(s2[j] + t2) & 1023]) >> 10)
                ray[j] = r0 + ((r1 * sine[(sr[j] + tr) & 1023]) >> 10)   # 256ths: the fade, in streaks
            ur, ug, ub = c.up
            top = c.top
            for k in range(n):
                j = cols[k]
                d = ys[k] - edge[j]               # + below the edge, - above it
                if d >= 0:
                    if d < depth:
                        w = ray[j]
                        rs[k] += dr[d] * w
                        gs[k] += dg[d] * w
                        bs[k] += db[d] * w
                elif -d < top:
                    d = -d
                    w = ray[j]
                    rs[k] += ur[d] * w
                    gs[k] += ug[d] * w
                    bs[k] += ub[d] * w
        return [(rs[k] >> 8 if rs[k] < 65280 else 255, gs[k] >> 8 if gs[k] < 65280 else 255,
                 bs[k] >> 8 if bs[k] < 65280 else 255) for k in range(n)]


class Game(BaseGame):
    def __init__(self, board):
        BaseGame.__init__(self, board)
        self.sky = Sky(board.lights.has_lines)
        self.last = None
        self.drawn = None                 # (when, the colors) last worked out

    def event(self, controller, action, now):
        if action == "pick":
            self.sky.kick(now)

    def update(self, now):
        if self.last is None:
            self.sky.since = now          # (the quiet sky starts when the game does)
        else:
            self.sky.run(now, min(0.1, now - self.last))
        self.last = now

    def draw(self, lights, now):
        if self.drawn is None or now - self.drawn[0] >= 1.0 / DRAW_HZ or now < self.drawn[0]:
            self.drawn = (now, self.sky.colors())
        colors = self.drawn[1]
        per, spots = G.LEDS_PER_SPOT, G.SPOTS * G.LEDS_PER_SPOT
        for t in range(G.SPOTS):            # (geometry.led_places order: each spot's LEDs, then the lines)
            lights.spot(t, colors[t * per:t * per + per])
        for k in range(len(colors) - spots):
            lights.line(k, colors[spots + k])
        n = int(self.sky.activity() * G.BAR_LEDS + 0.5)
        bar = [KP[i] if i < n else OFF for i in range(G.BAR_LEDS)]
        for seat in range(1, G.SEATS + 1):
            lights.bar(seat, bar)

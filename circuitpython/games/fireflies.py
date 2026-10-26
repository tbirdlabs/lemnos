# Fireflies: an evening of fireflies over the island, for when nobody's playing (an attract screen, or a wall
# decoration). Set GAME = "fireflies" in config.py, or pick it in the game picker.
#
# Each firefly sits at one of the island's LEDs (any of them, not by hex; on the small board the line LEDs too) and
# glows on its own rhythm, about every 4 seconds, each a little faster or slower than the rest: a soft pulse that
# rises quickly and fades slowly, never a flash. An evening goes:
#   dusk      one firefly, alone. After a few glows another answers it from nearby, just after it glows, and the two
#             call back and forth; then another answers, and another. Then more start on their own, anywhere, each
#             on its own time, coming quicker as there are more, until the whole swarm is out (about 3 minutes).
#             (Only the first few answer: if all of them did, the swarm would come out already in step.)
#   gathering when one glows, the others near it (by distance on the board) are drawn a little earlier in their
#             rhythm, so the swarm slowly falls into step, patch by patch, as real fireflies do: from scattered
#             twinkling to clusters glowing together to the whole island breathing as one.
#   night     the island glows in step for a while,
#   late      then they go out one by one, there's a moment of dark, and the next evening starts with one firefly.
# They drift now and then to a nearby LED, while dark, so the clusters keep changing.
#
# Every bar shows how in step the swarm is: a light per tenth. Controls: pick starts the evening over.
#
# The rules are Swarm below, on its own (no lights), so they can be run and tuned on a computer:
#   py -3 -c "from games import fireflies; fireflies.sim()"

import math
import random
from gamehost import geometry as G
from gamehost.game import Game as BaseGame

OFF = (0, 0, 0)
GLOW = (170, 255, 20)                    # a firefly at its brightest
BAR_LIT = (60, 90, 6)
# Tuned with sim() for a slow, calm arc: about 7 glows a second over the island once all are out, each 1.7 s long.
# Weaker nudges alone don't slow the gathering, they stop it: with an 8% spread below about 0.04, each one's own
# rhythm wins and the swarm never gets in step; closer rhythms let weak nudges get there. Fewer fireflies (one per 5
# LEDs) are too sparse for the clusters to join up.
PERIOD = 4.0                             # seconds between a firefly's glows, on average
SPREAD = 0.03                            # each one's own rhythm, within this share of PERIOD
NUDGE = 0.04                             # a neighbor's glow moves a firefly this share of its cycle earlier
NEAR = 1.6                               # how near counts as a neighbor, in hex widths
DEAF = 0.2                               # just after glowing, a firefly ignores its neighbors for this share of its cycle
RISE = 0.3                               # seconds a glow takes to brighten
FADE = 1.4                               # and to fade
HOP_S = 15.0                             # seconds between a firefly's moves, on average
HOP = 0.6                                # how far it moves at most, in hex widths
SHARE = 4                                # one firefly for every SHARE LEDs
# The evening
FIRST_ANSWER_S = 12.0                    # the first firefly glows alone this long before one answers
ALL_OUT_S = 180.0                        # the whole swarm is out this long after the first answer
ANSWER_AFTER = (0.5, 1.2)                # an answer glows this many seconds after the glow it answers
ANSWERS = 4                              # the first this many out answer; the rest start on their own
IN_STEP = 0.93                           # the swarm counts as in step at this (0-1: how closely its glows line up)
NIGHT_S = 45.0                           # glowing in step this long, then late
LONGEST_S = 900.0                        # late anyway, this long after all are out, if they never got in step
LATE_S = 60.0                            # going out one by one takes this long
DARK_S = 8.0                             # dark between evenings


def out_by(s, count):
    """How many fireflies are out s seconds into dusk: one, a second after FIRST_ANSWER_S, then more and more
    quickly (doubling at a steady rate) to all of them ALL_OUT_S after that."""
    if s < FIRST_ANSWER_S:
        return 1
    k = (s - FIRST_ANSWER_S) / ALL_OUT_S
    return min(count, int(2 * (count / 2.0) ** k))


class Swarm:
    """The fireflies: each one's place (an index into G.led_places), rhythm, phase (0-1, it glows at 1), when it last
    glowed, and whether it's out. `part` is the part of the evening: dusk, gathering, night, late, dark."""

    def __init__(self, has_lines=False, rng=random):
        self.rng = rng
        self.places = G.led_places(has_lines)
        n = len(self.places)
        self.near_place = [[j for j in range(n) if j != i and self.dist(i, j) <= HOP] for i in range(n)]
        count = n // SHARE
        self.at = []
        free = list(range(n))
        for _ in range(count):
            self.at.append(free.pop(int(rng.random() * len(free))))
        self.period = [PERIOD * (1 + SPREAD * (2 * rng.random() - 1)) for _ in range(count)]
        self.phase = [0.0] * count
        self.lit = [-9.0] * count          # when each last glowed
        self.out = [False] * count
        self.next_hop = [rng.random() * 2 * HOP_S for _ in range(count)]
        self.evenings = 0
        self.evening(0.0)

    def to(self, part, now):
        self.part = part
        self.since = now                   # when this part of the evening began
        self.began[part] = now

    def evening(self, now):
        """A new evening: everyone in, then one firefly out, glowing soon."""
        self.began = {}                    # when each part of this evening began
        self.to("dusk", now)
        self.evenings += 1
        for f in range(len(self.at)):
            self.out[f] = False
        f = int(self.rng.random() * len(self.at))
        self.out[f] = True
        self.phase[f] = 0.85
        self.step_now = 0.0                # in_step(), as of the last run()

    def dist(self, i, j):
        a, b = self.places[i], self.places[j]
        return math.sqrt((a[2] - b[2]) ** 2 + (a[3] - b[3]) ** 2)

    def count_out(self):
        return sum(1 for x in self.out if x)

    def in_step(self):
        """0-1: how closely the glows of the fireflies out line up (1: all at once); 0 with fewer than 3 out."""
        c = s = 0.0
        n = 0
        for f, p in enumerate(self.phase):
            if self.out[f]:
                c += math.cos(6.2832 * p)
                s += math.sin(6.2832 * p)
                n += 1
        return math.sqrt(c * c + s * s) / n if n >= 3 else 0.0

    def scatter(self):
        """New phases at random for every firefly out."""
        for f in range(len(self.at)):
            if self.out[f]:
                self.phase[f] = self.rng.random()

    def come_out(self, f):
        """A firefly not out yet comes out: while there are few, it answers f from near it, glowing just after it;
        after that, wherever it is, on its own time."""
        rng = self.rng
        waiting = [g for g in range(len(self.at)) if not self.out[g]]
        if not waiting:
            return
        g = waiting[int(rng.random() * len(waiting))]
        if self.count_out() < ANSWERS:
            taken = set(self.at[h] for h in range(len(self.at)) if self.out[h])
            here = self.at[f]                 # (worked out now, not kept: a list for every LED is a lot of memory)
            free = [j for j in range(len(self.places)) if j not in taken and j != here and self.dist(here, j) <= NEAR]
            if free:
                self.at[g] = free[int(rng.random() * len(free))]
            after = ANSWER_AFTER[0] + rng.random() * (ANSWER_AFTER[1] - ANSWER_AFTER[0])
            self.phase[g] = 1.0 - after / self.period[g]
        else:
            self.phase[g] = rng.random() * 0.9
        self.out[g] = True
        self.lit[g] = -9.0

    def run(self, now, dt):
        """dt seconds more, to the board's clock `now`."""
        rng = self.rng
        n = len(self.at)
        s = now - self.since
        if self.part == "dark":
            if s >= DARK_S:
                self.evening(now)
            return
        glowing = []
        for f in range(n):
            if self.out[f]:
                self.phase[f] += dt / self.period[f]
                if self.phase[f] >= 1.0:
                    glowing.append(f)
        k = 0
        while k < len(glowing):           # each glow nudges its neighbors; one nudged past 1 glows too, at once
            f = glowing[k]
            k += 1
            self.phase[f] = 0.0
            self.lit[f] = now
            for g in range(n):
                if g == f or not self.out[g] or self.phase[g] < DEAF or g in glowing:
                    continue
                if self.dist(self.at[f], self.at[g]) <= NEAR:
                    self.phase[g] += NUDGE
                    if self.phase[g] >= 1.0:
                        glowing.append(g)
        out = self.count_out()
        if self.part == "dusk":
            for f in glowing:             # new ones come out with glows, as many as the evening has reached
                if out < out_by(s, n):
                    self.come_out(f)
                    out += 1
            if out >= n:
                self.to("gathering", now)
        elif self.part == "late":         # one by one, each as it finishes a glow
            want = n - int(n * min(1.0, s / LATE_S))
            for f in glowing:
                if out > want:
                    self.out[f] = False
                    out -= 1
            if out == 0 and now - max(self.lit) > RISE + FADE:
                self.to("dark", now)
        taken = set(self.at)
        for f in range(n):                # drifting, while dark
            if now >= self.next_hop[f] and now - self.lit[f] > RISE + FADE:
                self.next_hop[f] = now + HOP_S * (0.5 + rng.random())
                free = [j for j in self.near_place[self.at[f]] if j not in taken]
                if free:
                    taken.discard(self.at[f])
                    self.at[f] = free[int(rng.random() * len(free))]
                    taken.add(self.at[f])
        self.step_now = self.in_step()
        if self.part == "gathering":
            if self.step_now >= IN_STEP:
                self.to("night", now)
            elif s >= LONGEST_S:
                self.to("late", now)
        elif self.part == "night":
            if s >= NIGHT_S:
                self.to("late", now)

    def brightness(self, f, now):
        """0-1: firefly f's glow at `now`."""
        s = now - self.lit[f]
        if s < 0 or s >= RISE + FADE:
            return 0.0
        if s < RISE:
            return s / RISE
        k = 1.0 - (s - RISE) / FADE
        return k * k


def card(lights, now):
    """The board's game picker shows this (gamehost/lobby.py): a few fireflies, one cluster glowing together."""
    for t, i, k in (("B2", 0, 1.0), ("B2", 2, 0.8), ("C2", 1, 1.0), ("C3", 0, 0.7), ("E5", 1, 0.3), ("F2", 2, 0.5),
                    ("D6", 0, 0.2), ("A3", 1, 0.4)):
        c = [OFF, OFF, OFF]
        c[i] = (int(GLOW[0] * k), int(GLOW[1] * k), int(GLOW[2] * k))
        lights.spot(t, c)


class Game(BaseGame):
    def __init__(self, board):
        BaseGame.__init__(self, board)
        self.swarm = Swarm(board.lights.has_lines)
        self.last = None

    def event(self, controller, action, now):
        if action == "pick":
            self.swarm.evening(now)

    def update(self, now):
        if self.last is None:
            self.swarm.since = now         # (the evening starts when the game does)
        else:
            self.swarm.run(now, min(0.1, now - self.last))
        self.last = now

    def draw(self, lights, now):
        sw = self.swarm
        spots = {}
        for f in range(len(sw.at)):
            b = sw.brightness(f, now)
            if b <= 0:
                continue
            t, i = sw.places[sw.at[f]][:2]
            c = (int(GLOW[0] * b), int(GLOW[1] * b), int(GLOW[2] * b))
            if t is None:
                lights.line(i, c)
            else:
                spots.setdefault(t, [OFF, OFF, OFF])[i] = c
        for t, c in spots.items():
            lights.spot(t, c)
        n = int(sw.step_now * G.BAR_LEDS + 0.5)
        bar = [BAR_LIT if i < n else OFF for i in range(G.BAR_LEDS)]
        for seat in range(1, G.SEATS + 1):
            lights.bar(seat, bar)


def sim(seconds=4 * 3600, seed=1, has_lines=False, dt=0.025):
    """The rules on a computer: how each evening goes (how long to all out, then to in step), and how many there are."""
    sw = Swarm(has_lines, random.Random(seed))
    now = 0.0
    evenings = []                         # each evening's sw.began, when it ends
    first = []                            # how many are out at 30, 60, 90, 120 s into the first dusk
    seen = sw.evenings
    began = sw.began
    for k in range(int(seconds / dt)):
        now += dt
        sw.run(now, dt)
        if sw.evenings == 1:
            for mark in (30, 60, 90, 120):
                if abs(now - mark) < dt / 2:
                    first.append(sw.count_out())
        if sw.evenings != seen:
            evenings.append(began)
            seen = sw.evenings
        began = sw.began
    q = lambda xs, p: sorted(xs)[min(len(xs) - 1, int(p * len(xs)))] if xs else -1
    outs = [e["gathering"] - e["dusk"] for e in evenings if "gathering" in e]
    steps = [e["night"] - e["gathering"] for e in evenings if "night" in e]
    whole = [e["dark"] + DARK_S - e["dusk"] for e in evenings if "dark" in e]
    print("%d fireflies on %d LEDs, %.1f h: %d evenings" % (len(sw.at), len(sw.places), seconds / 3600, len(evenings)))
    print("the first dusk, out at 30/60/90/120 s: %s" % first)
    print("all out after %.0f s; then in step after median %.0f s (90%% %.0f s); never in step: %d" % (
        q(outs, 0.5), q(steps, 0.5), q(steps, 0.9), len(evenings) - len(steps)))
    print("an evening: median %.0f s (10%% %.0f s, 90%% %.0f s)" % (q(whole, 0.5), q(whole, 0.1), q(whole, 0.9)))

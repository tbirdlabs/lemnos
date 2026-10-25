# Forest fire: the island as a living forest, for when nobody's playing (an attract screen, or a wall decoration).
# Set GAME = "fire" in config.py, or pick it in the game picker.
#
# Every half second (a tick): bare ground sprouts, more readily next to forest (seeds spread); forest thickens, from
# 1 light to 3; now and then lightning strikes, and a strike on forest starts a fire. Fire spreads to the forest
# around it, more readily the thicker it is, and burns longer in thick forest; a burnt spot cools through embers to
# bare ground, and the forest grows back. Thick forest burns big, so the island swings between grown over and burnt
# out, and no two fires are alike. Every light fades into its next color over a tick, and fire flickers slowly (well
# under the board's flash limit, fx.MAX_FLASHES_PER_S).
#
# The lights: forest is green, 1 to 3 lights a spot as it thickens (as in Island Rush); fire orange to red as it
# burns down; embers a dim red; bare ground dark. A strike shows as one short white flash. Every bar shows the island
# at a glance: green for forest (how much of the island), orange from the far end for fire.
#
# Controls: pick calls down lightning on a thick part of the forest (once a second at most).
#
# The rules are step() below, on its own (no lights, no clock), so they can be run and tuned on a computer:
#   py -3 -c "from games import fire; fire.sim()"

import math
import random
from gamehost import geometry as G
from gamehost.game import Game as BaseGame

OFF = (0, 0, 0)
TICK_S = 0.5                             # seconds a step of the forest takes

# The rules, per tick. Forest thickness 1-3. Tuned with sim() (8 hours): mostly green (median 33 of 37 spots
# forest), a fire every 24 s or so, most small (median 5 spots), 1 in 4 of 17 or more, 1 in 14 the whole island.
# Thin forest hardly carries fire, so quick sprouting and slow thickening keep fires patchy; more lightning makes
# them smaller and more often, faster thickening bigger.
SPROUT = 0.012                           # bare ground sprouts by itself (a seed blown in)
SPROUT_NEAR = 0.09                       # and this much more for each thick (2-3) neighbor
THICKEN = (0.0, 0.0125, 0.006)           # forest thickens 1 -> 2, 2 -> 3
LIGHTNING = 0.03                         # a strike somewhere on the island
CATCH = (0.0, 0.03, 0.12, 0.45)          # a burning neighbor sets forest this thick alight
BURN = (0, 2, 3, 5)                      # ticks a spot burns, by how thick it was
EMBERS = 8                               # ticks a burnt spot glows before it's bare ground

FOREST = ((0, 0, 0), (40, 150, 10), (0, 130, 20), (0, 110, 30))     # young, then darker as it thickens
LIT = ((False, False, False), (False, True, False), (True, False, True), (True, True, True))   # 0-3 lights
FIRE_HOT = (255, 110, 0)
FIRE_LOW = (180, 20, 0)
EMBER = (50, 6, 0)
STRIKE = (255, 255, 255)
STRIKE_S = 0.15                          # the strike's flash
FLICKER_HZ = 0.9                         # fire's slow shimmer
BAR_FOREST = (0, 140, 20)
BAR_FIRE = (255, 90, 0)


class Forest:
    """The forest's state: per spot, thickness 0-3, ticks left burning (0: not), ticks left as embers (0: not)."""

    def __init__(self, rng=random):
        self.rng = rng
        self.tree = [0] * G.SPOTS
        self.fire = [0] * G.SPOTS
        self.burnt = [0] * G.SPOTS        # how thick it was, while it burns (for its colors)
        self.ember = [0] * G.SPOTS
        self.struck = -1                  # the spot lightning hit this tick, or -1
        for t in range(G.SPOTS):          # start part grown, unevenly
            if rng.random() < 0.5:
                self.tree[t] = 1 + int(rng.random() * 3)

    def strike(self, t):
        """Lightning on spot t: forest there catches."""
        self.struck = t
        if self.tree[t] and not self.fire[t]:
            self.burnt[t] = self.tree[t]
            self.fire[t] = BURN[self.tree[t]]
            self.tree[t] = 0

    def thickest(self):
        """A spot of the thickest forest there is (for a strike called down), or -1."""
        best = max(self.tree)
        spots = [t for t in range(G.SPOTS) if self.tree[t] == best] if best else []
        return spots[int(self.rng.random() * len(spots))] if spots else -1

    def step(self):
        """One tick of the forest."""
        rng = self.rng
        tree, fire, ember = self.tree, self.fire, self.ember
        self.struck = -1
        catching = []
        for t in range(G.SPOTS):
            if fire[t]:
                for n in G.NEIGHBORS[t]:
                    if tree[n] and not fire[n] and rng.random() < CATCH[tree[n]]:
                        catching.append(n)
        for t in range(G.SPOTS):
            if fire[t]:
                fire[t] -= 1
                if not fire[t]:
                    ember[t] = EMBERS
            elif ember[t]:
                ember[t] -= 1
            elif tree[t]:
                if tree[t] < 3 and rng.random() < THICKEN[tree[t]]:
                    tree[t] += 1
            else:
                near = sum(1 for n in G.NEIGHBORS[t] if tree[n] >= 2)
                if rng.random() < SPROUT + SPROUT_NEAR * near:
                    tree[t] = 1
        for n in catching:
            if tree[n] and not fire[n]:
                self.burnt[n] = tree[n]
                fire[n] = BURN[tree[n]]
                tree[n] = 0
        if rng.random() < LIGHTNING:
            self.strike(int(rng.random() * G.SPOTS))

    def cover(self):
        """(spots of forest, spots burning)."""
        return sum(1 for x in self.tree if x), sum(1 for x in self.fire if x)


def mix(a, b, f):
    return (a[0] + int((b[0] - a[0]) * f), a[1] + int((b[1] - a[1]) * f), a[2] + int((b[2] - a[2]) * f))


def colors(forest, t):
    """Spot t's 3 colors after this tick, before the flicker. Burning spots are marked by forest.fire."""
    if forest.fire[t]:
        heat = forest.fire[t] / BURN[forest.burnt[t]]
        c = mix(FIRE_LOW, FIRE_HOT, heat)
        n = forest.burnt[t]
        return [c if LIT[max(n, 2)][i] or heat > 0.5 else EMBER for i in range(3)]
    if forest.ember[t]:
        c = mix(OFF, EMBER, forest.ember[t] / EMBERS)
        return [c, c, c]
    n = forest.tree[t]
    return [FOREST[n] if LIT[n][i] else OFF for i in range(3)]


def card(lights, now):
    """The board's game picker shows this (gamehost/lobby.py): forest with a fire in it."""
    for t in range(G.SPOTS):
        n = 1 + (G.Q[t] * 7 + G.R[t] * 3) % 3
        lights.spot(t, [FOREST[n] if LIT[n][i] else OFF for i in range(3)])
    for t in ("C3", "D4", "D3"):
        lights.spot(t, [FIRE_HOT] * 3)
    lights.spot("C4", [EMBER] * 3)


class Game(BaseGame):
    def __init__(self, board):
        BaseGame.__init__(self, board)
        self.forest = Forest()
        self.before = [colors(self.forest, t) for t in range(G.SPOTS)]
        self.after = self.before
        self.at = None                    # when this tick started
        self.flash_at = -1.0              # the strike's flash: when, and where
        self.flash_spot = -1
        self.called = -9.0                # the last strike called down with pick

    def event(self, controller, action, now):
        if action == "pick" and now - self.called >= 1.0:
            t = self.forest.thickest()
            if t >= 0:
                self.called = now
                self.forest.strike(t)
                self.flash_at, self.flash_spot = now, t
                self.after = [colors(self.forest, s) for s in range(G.SPOTS)]

    def update(self, now):
        if self.at is None:
            self.at = now
        while now - self.at >= TICK_S:   # (catches up a tick at a time, after a pause)
            self.at += TICK_S
            self.before = self.after
            self.forest.step()
            self.after = [colors(self.forest, t) for t in range(G.SPOTS)]
            if self.forest.struck >= 0:
                self.flash_at, self.flash_spot = self.at, self.forest.struck

    def draw(self, lights, now):
        f = 0.0 if self.at is None else min(1.0, (now - self.at) / TICK_S)
        fire = self.forest.fire
        for t in range(G.SPOTS):
            if t == self.flash_spot and 0 <= now - self.flash_at < STRIKE_S:
                lights.spot(t, [STRIKE] * 3)
                continue
            a, b = self.before[t], self.after[t]
            out = [mix(a[i], b[i], f) for i in range(3)]
            if fire[t]:                   # a slow shimmer, each light on its own phase
                for i in range(3):
                    k = 0.75 + 0.25 * math.sin(6.2832 * FLICKER_HZ * now + t * 1.7 + i * 2.1)
                    c = out[i]
                    out[i] = (int(c[0] * k), int(c[1] * k), int(c[2] * k))
            lights.spot(t, out)
        trees, burning = self.forest.cover()
        g = (trees * G.BAR_LEDS + G.SPOTS // 2) // G.SPOTS
        r = min(G.BAR_LEDS, (burning * G.BAR_LEDS + G.SPOTS - 1) // G.SPOTS)
        bar = [BAR_FIRE if i >= G.BAR_LEDS - r else BAR_FOREST if i < g else OFF for i in range(G.BAR_LEDS)]
        for seat in range(1, G.SEATS + 1):
            lights.bar(seat, bar)


def sim(ticks=200000, seed=1):
    """The rules on a computer: how often fires start, how big they get, how much forest there is."""
    f = Forest(random.Random(seed))
    fires = []                            # (start tick, spots burnt)
    burning = 0
    covers = []
    for k in range(ticks):
        was = burning
        f.step()
        trees, burning = f.cover()
        covers.append(trees)
        new = sum(1 for t in range(G.SPOTS) if f.fire[t] == BURN[f.burnt[t]] and f.burnt[t])
        if burning and not was:
            fires.append([k, 0])
        if fires and (burning or was):
            fires[-1][1] += new
    sizes = sorted(s for _, s in fires)
    gaps = sorted(b[0] - a[0] for a, b in zip(fires, fires[1:]))
    covers.sort()
    q = lambda xs, p: xs[min(len(xs) - 1, int(p * len(xs)))] if xs else 0
    print("%d ticks (%.1f h): %d fires, one every %.0f s (median gap %.0f s)" % (
        ticks, ticks * TICK_S / 3600, len(fires), ticks * TICK_S / max(1, len(fires)), q(gaps, 0.5) * TICK_S))
    print("spots burnt per fire: median %d, 75%% %d, 90%% %d, max %d; whole-island fires (30+): %d%%" % (
        q(sizes, 0.5), q(sizes, 0.75), q(sizes, 0.9), q(sizes, 1.0), 100 * sum(1 for s in sizes if s >= 30) //
        max(1, len(sizes))))
    print("forest cover (of 37): 10%% %d, median %d, 90%% %d" % (q(covers, 0.1), q(covers, 0.5), q(covers, 0.9)))

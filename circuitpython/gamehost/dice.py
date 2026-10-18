# The die roller for any game: a white light runs along a seat's bar, then laps again and slows to stop on the
# result, and holds there for a moment. Salient shows its d10 this way over the chance (green out of 10).
#
#   roll = dice.Roll(now, result)              # result 1..n (n = 10 for a bar); the game rolls it however it likes
#   ... every frame:  roll.draw(lights, seat, background)   # background: the bar's 10 colors under the light
#   roll.done(now)                              # True once it has landed and held
#   roll.duration                               # seconds from start to done (to schedule what comes next)
#
# dice.d(n) rolls 1..n for games that don't keep their own random numbers. dice.seed() is a random 32-bit number
# to start a game's own generator with (Salient seeds its engine's d10 with it, so a game can be replayed from its
# seed). The timing follows config.EFFECT_TIME_SCALE, like every effect.

import config

WHITE = (255, 255, 255)
STEP = 0.045          # seconds per light while it runs fast
SLOW = 0.035          # extra seconds per light over the last 6, so it slows to a stop
HOLD = 0.75           # seconds it stays on the result


def d(n):
    """A random roll 1..n."""
    try:
        import os
        b = os.urandom(2)
        return 1 + (b[0] << 8 | b[1]) % n
    except Exception:
        import random
        return random.randint(1, n)


def seed():
    """A random number 0..2**32-1, to seed a game's own random numbers."""
    try:
        import os
        b = os.urandom(4)
        return (b[0] | b[1] << 8 | b[2] << 16 | b[3] << 24) & 0xFFFFFFFF
    except Exception:
        import time
        return int(time.monotonic() * 1000) & 0xFFFFFFFF


class Roll:
    def __init__(self, now, result, n=10, laps=1, color=WHITE):
        """result: 1..n, where it stops. laps: full runs along the bar before the last one."""
        k = getattr(config, "EFFECT_TIME_SCALE", 1.0)
        positions = list(range(n)) * laps + list(range(result))
        self.color = color
        self.result = result
        self.times = []                       # when each position lights
        t = now
        for i in range(len(positions)):
            self.times.append(t)
            left = len(positions) - i
            t += (STEP if left > 6 else STEP + (7 - left) * SLOW) * k
        self.positions = positions
        self.landed_at = self.times[-1] if self.times else now
        self.end = t + HOLD * k
        self.duration = self.end - now

    def position(self, now):
        """The lit light's index along the bar (0 = LED 1), or -1 before it starts."""
        pos = -1
        for i, t in enumerate(self.times):
            if now >= t:
                pos = self.positions[i]
            else:
                break
        return pos

    def done(self, now):
        return now >= self.end

    def draw(self, lights, seat, background, now=None):
        """The bar with the running light over `background` (10 colors)."""
        now = lights.now if now is None else now
        out = list(background)
        p = self.position(now)
        if p >= 0:
            out[p] = self.color
        lights.bar(seat, out)

# Light effects. A game passes an effect along with a color, and the light layer works out what the LED shows right
# now, from the board's one clock (so every LED with the same effect and speed stays in step):
#
#   lights.spot(t, colors, fx.breathe(3))           # a 3-second breath
#   lights.spot(t, colors, fx.blink(fx.FAST))       # named speeds: SLOW, NORMAL, FAST (seconds per cycle)
#   lights.bar(seat, colors, fx.chase(1))           # a light running along the bar once a second
#   lights.spot(t, colors, [fx.STEADY, fx.flash(0.5), fx.STEADY])   # one effect per LED
#
# The patterns here are examples; add your own by subclassing Effect and writing at(color, phase, i, n).
#
# Two board-wide settings in config.py:
#   EFFECT_TIME_SCALE  multiplies every effect's cycle time (1.5 = everything 1.5x slower, for a player who needs
#                      more time to read the board)
#   No effect that switches lights on and off runs faster than 3 times a second: flashing between 3 and 30 times a
#   second can set off photosensitive seizures. Effect.on_off marks the ones the limit applies to.

import config

SLOW = 3.0
NORMAL = 1.5
FAST = 0.6
MAX_FLASHES_PER_S = 3
WHITE = (255, 255, 255)
OFF = (0, 0, 0)


def scale(c, k):
    """Color c at brightness k (0..1)."""
    return (int(c[0] * k), int(c[1] * k), int(c[2] * k))


class Effect:
    """period: seconds per cycle. on_off: the effect switches lights between two states (the flash limit applies)."""
    on_off = False

    def __init__(self, period=NORMAL):
        p = period * getattr(config, "EFFECT_TIME_SCALE", 1.0)
        if self.on_off:
            p = max(p, 1.0 / MAX_FLASHES_PER_S)
        self.period = p

    def color(self, c, now, i=0, n=1):
        """The color an LED drawn as c shows at time now. i, n: its place in the group drawn together
        (0-2 of a spot's 3, 0-9 of a bar's 10), for effects that move along a group."""
        if self.period <= 0:
            return c
        return self.at(c, (now / self.period) % 1.0, i, n)

    def at(self, c, phase, i, n):
        """phase: 0..1 through the cycle. Override this for a new effect."""
        return c


class _Steady(Effect):
    def color(self, c, now, i=0, n=1):
        return c


STEADY = _Steady(0)


class blink(Effect):
    """On for `duty` of the cycle, off for the rest."""
    on_off = True

    def __init__(self, period=NORMAL, duty=0.5):
        Effect.__init__(self, period)
        self.duty = duty

    def at(self, c, phase, i, n):
        return c if phase < self.duty else OFF


class breathe(Effect):
    """A smooth fade down to `low` (0..1) and back up, never fully dark."""

    def __init__(self, period=NORMAL, low=0.3):
        Effect.__init__(self, period)
        self.low = low

    def at(self, c, phase, i, n):
        k = abs(phase * 2 - 1)                      # 1 at the ends of the cycle, 0 in the middle
        k = k * k * (3 - 2 * k)                     # eased
        return scale(c, self.low + (1 - self.low) * k)


class flash(Effect):
    """Swaps between the color and `other` (white by default): `other` for `duty` of the cycle."""
    on_off = True

    def __init__(self, period=NORMAL, other=WHITE, duty=0.4):
        Effect.__init__(self, period)
        self.other = other
        self.duty = duty

    def at(self, c, phase, i, n):
        return self.other if phase < self.duty else c


class chase(Effect):
    """One light running along the group once a cycle (LED 1 first); the others dark.
    `tail` lights trail it, dimmer. reverse runs it the other way."""

    def __init__(self, period=NORMAL, tail=0, reverse=False):
        Effect.__init__(self, period)
        self.tail = tail
        self.reverse = reverse

    def at(self, c, phase, i, n):
        head = int(phase * n)
        if self.reverse:
            head = n - 1 - head
            d = i - head
        else:
            d = head - i
        if d == 0:
            return c
        if 0 < d <= self.tail:
            return scale(c, 1.0 / (d + 1))
        return OFF

# The board's lights: the island's 37 spots (3 LEDs each) and six 10-light bars, one per seat.
# Games draw by spot and by seat; this module knows the wiring (docs/wiring.md) and nothing about any game.
#   lights.spot(t, colors)      3 (r, g, b) for spot t (the engine's numbering: row by row from A1, left to right
#                               as seen from seat 1); light 0 is the left one, as seen from seat 1
#   lights.bar(seat, colors)    10 (r, g, b) for seat 1-6; light 0 is LED 1, at the player's left
#   lights.fill(color), lights.show()
# show() sends only what changed, and dims the whole frame if it would draw more than config.POWER_LIMIT_A.

import config

SPOTS = 37
PER_SPOT = 3
SEATS = 6
BAR = 10
ROW_LENGTHS = (4, 5, 6, 7, 6, 5, 4)
ISLAND = SPOTS * PER_SPOT            # 111
COUNT = ISLAND + SEATS * BAR         # 171 logical LEDs
STRAND = ISLAND                      # NeoPXL8 gives every channel the same length
OFF = (0, 0, 0)
_DARK = bytes(COUNT * 3)

try:
    import board
    from adafruit_neopxl8 import NeoPxl8
    HARDWARE = True
except ImportError:                  # desktop Python: lights are kept in memory only
    HARDWARE = False


def _physical_map():
    """PHYS[k] = index in the NeoPXL8 buffer of logical LED k."""
    phys = [0] * COUNT
    base = config.ISLAND_CHANNEL * STRAND
    t = 0
    pos = 0
    for r, n in enumerate(ROW_LENGTHS):
        right = r % 2 == 0                       # A, C, E, G run right; B, D, F run left
        for c in range(n):
            spot = t + c
            k = c if right else n - 1 - c        # this spot's place along the run
            for i in range(PER_SPOT):
                phys[spot * PER_SPOT + i] = base + pos + k * PER_SPOT + (i if right else PER_SPOT - 1 - i)
        t += n
        pos += n * PER_SPOT
    for s in range(SEATS):
        b = config.BAR_CHANNELS[s] * STRAND
        for i in range(BAR):
            phys[ISLAND + s * BAR + i] = b + i
    return phys


class Lights:
    def __init__(self):
        self.raw = bytearray(COUNT * 3)          # what the game drew this frame
        self.sent = bytearray(COUNT * 3)         # what the LEDs show
        self.phys = _physical_map()
        self.pixels = None
        self.scale = 1.0
        if HARDWARE:
            pin = getattr(board, config.LED_FIRST_PIN)
            self.pixels = NeoPxl8(pin, STRAND * 8, num_strands=8, auto_write=False,
                                  brightness=config.BRIGHTNESS, pixel_order=config.PIXEL_ORDER)
            self.pixels.fill(OFF)
            self.pixels.show()

    def _set(self, k, c):
        j = k * 3
        self.raw[j] = c[0]
        self.raw[j + 1] = c[1]
        self.raw[j + 2] = c[2]

    def spot(self, t, colors):
        for i in range(PER_SPOT):
            self._set(t * PER_SPOT + i, colors[i])

    def bar(self, seat, colors):
        base = ISLAND + (seat - 1) * BAR
        for i in range(BAR):
            self._set(base + i, colors[i])

    def fill(self, c):
        if c == OFF:
            self.raw[:] = _DARK
            return
        for k in range(COUNT):
            self._set(k, c)

    def milliamps(self):
        """Estimated LED current for the frame as drawn, at full scale."""
        return COUNT * config.MA_IDLE + sum(self.raw) * config.BRIGHTNESS * config.MA_PER_CHANNEL / 255

    def show(self):
        limit = config.POWER_LIMIT_A
        scale = 1.0
        if limit:
            ma = self.milliamps()
            budget = limit * 1000
            if ma > budget:
                idle = COUNT * config.MA_IDLE
                scale = max(0.0, (budget - idle) / (ma - idle))
        if self.pixels is None:
            self.scale = scale
            self.sent[:] = self.raw
            return
        changed = False
        if scale != self.scale:
            self.scale = scale
            self.pixels.brightness = config.BRIGHTNESS * scale
            changed = True
        raw = self.raw
        sent = self.sent
        px = self.pixels
        phys = self.phys
        for k in range(COUNT):
            j = k * 3
            if raw[j] != sent[j] or raw[j + 1] != sent[j + 1] or raw[j + 2] != sent[j + 2]:
                px[phys[k]] = (raw[j], raw[j + 1], raw[j + 2])
                changed = True
        if changed:
            sent[:] = raw
            px.show()

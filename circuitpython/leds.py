# The board's lights: the island's 37 spots (3 LEDs each), six 10-light bars (one per seat), and, on the
# 144 LEDs/m map, one LED on every vertical line between spots (and at each row's two ends).
# Games draw by spot, by seat and by line; this module knows the wiring (docs/wiring.md) and nothing about any game.
#   lights.spot(t, colors)      3 (r, g, b) for spot t (the engine's numbering: row by row from A1, left to right
#                               as seen from seat 1); light 0 is the left one, as seen from seat 1
#   lights.bar(seat, colors)    10 (r, g, b) for seat 1-6; light 0 is LED 1, at the player's left
#   lights.line(row, k, color)  the line LED k (0 = the row's left end, as seen from seat 1) in row 0-6 (A-G);
#                               the line between spot t and its right-hand neighbor is (ROW of t, its column + 1).
#                               Does nothing on a map without line LEDs (LINES == 0).
#   lights.fill(color), lights.show()
# spot, bar and line also take an effect (fx.py): one for the whole group, or a list with one per LED, e.g.
#   lights.spot(t, colors, fx.breathe(3)). Effects run off lights.now, the board's clock (the host sets it).
# show() sends only what changed, and dims the whole frame if it would draw more than config.POWER_LIMIT_A.
#
# config.LED_MAP picks the island's LED map (the bars are the same on both):
#   "60_leds_per_meter"   3 LEDs a spot: rows of 12, 15, 18, 21, 18, 15, 12 LEDs (111)
#   "144_leds_per_meter"  a line LED, a spot's 3, a line LED, ... a line LED: rows of 17, 21, 25, 29, 25, 21, 17 (155)

import config

SPOTS = 37
PER_SPOT = 3
SEATS = 6
BAR = 10
ROW_LENGTHS = (4, 5, 6, 7, 6, 5, 4)
OFF = (0, 0, 0)
MAPS = ("60_leds_per_meter", "144_leds_per_meter")


def layout(name):
    """For an LED map: (island LEDs on the strip, line LEDs, PHYS) where PHYS[k] is the NeoPXL8 buffer index of
    logical LED k. Logical order: spots (37 x 3), then bars (6 x 10), then lines (row by row, left to right)."""
    if name not in MAPS:
        raise ValueError("config.LED_MAP must be one of %s" % (MAPS,))
    lines = name == "144_leds_per_meter"
    nlines = sum(n + 1 for n in ROW_LENGTHS) if lines else 0
    island = sum(n * PER_SPOT + (n + 1 if lines else 0) for n in ROW_LENGTHS)
    strand = island                              # NeoPXL8 gives every channel the same length
    phys = [0] * (SPOTS * PER_SPOT + SEATS * BAR + nlines)
    base = config.ISLAND_CHANNEL * strand
    first_line = SPOTS * PER_SPOT + SEATS * BAR
    t = 0
    ln = 0
    pos = base
    for r, n in enumerate(ROW_LENGTHS):
        right = r % 2 == 0                       # A, C, E, G run right; B, D, F run left
        run = []                                 # this row's logical LEDs, left to right as seen from seat 1
        for c in range(n):
            if lines:
                run.append(first_line + ln + c)
            for i in range(PER_SPOT):
                run.append((t + c) * PER_SPOT + i)
        if lines:
            run.append(first_line + ln + n)
        if not right:
            run.reverse()
        for k in run:
            phys[k] = pos
            pos += 1
        t += n
        ln += n + 1 if lines else 0
    for s in range(SEATS):
        b = config.BAR_CHANNELS[s] * strand
        for i in range(BAR):
            phys[SPOTS * PER_SPOT + s * BAR + i] = b + i
    return island, nlines, phys


ISLAND_LEDS, LINES, PHYS = layout(config.LED_MAP)
STRAND = ISLAND_LEDS
ISLAND = SPOTS * PER_SPOT                # first logical bar LED
FIRST_LINE = ISLAND + SEATS * BAR
COUNT = FIRST_LINE + LINES               # 171 or 215 logical LEDs
LINE_START = []
_n = 0
for _len in ROW_LENGTHS:
    LINE_START.append(_n)
    _n += _len + 1
_DARK = bytes(COUNT * 3)

try:
    import board
    from adafruit_neopxl8 import NeoPxl8
    HARDWARE = True
except ImportError:                  # desktop Python: lights are kept in memory only
    HARDWARE = False


class Lights:
    def __init__(self):
        self.raw = bytearray(COUNT * 3)          # what the game drew this frame
        self.sent = bytearray(COUNT * 3)         # what the LEDs show
        self.phys = PHYS
        self.pixels = None
        self.scale = 1.0
        self.now = 0.0                           # the board's clock, for effects; the host sets it every frame
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

    def _group(self, base, colors, effect, n):
        if effect is None:
            for i in range(n):
                self._set(base + i, colors[i])
            return
        each = isinstance(effect, (list, tuple))
        now = self.now
        for i in range(n):
            e = effect[i] if each else effect
            self._set(base + i, colors[i] if e is None else e.color(colors[i], now, i, n))

    def spot(self, t, colors, effect=None):
        self._group(t * PER_SPOT, colors, effect, PER_SPOT)

    def bar(self, seat, colors, effect=None):
        self._group(ISLAND + (seat - 1) * BAR, colors, effect, BAR)

    def line(self, row, k, color, effect=None):
        if LINES:
            self._set(FIRST_LINE + LINE_START[row] + k, color if effect is None else effect.color(color, self.now))

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

# The board's lights, for any game: the island's 37 hexes (3 LEDs each), six 10-light bars (one per seat), and, on
# the small board, one LED under every vertical line in each row (between hexes, and at each row's two ends).
# Games draw by name; this module knows the wiring (docs/wiring.md), serpentine included, and nothing about any game.
# Names are geometry.py's: rows A-G from farthest from seat 1 to nearest, hexes and lines counted from 1, left to
# right as seen from seat 1 (line Bk is just left of hex Bk). Numbers (geometry's) work anywhere a name does.
#   lights.spot("B3", colors)           3 (r, g, b), left to right as seen from seat 1
#   lights.line("B4", color)            one line LED (small board; nothing on the large board)
#   lights.between("B3", "B4", color)   the line LED between two hexes side by side in a row (here line B4)
#   lights.bar(seat, colors)            10 (r, g, b) for seat 1-6; light 0 is LED 1, at that player's left. Drawn
#                                       on the bar that seat has: its own, unless a controller carrying a bar sits
#                                       there (carry(), set by the lobby)
#   lights.bar_at(n, colors)            bar n itself (1-6, its place in BARS_AT), whichever seat has it
#   lights.has_lines                    True on the small board
#   lights.fill(color), lights.show()
# Colors are (r, g, b), each 0-255; lower is dimmer. spot, bar and line also take an effect (fx.py): one for the
# whole group, or a list with one per LED, e.g. lights.spot(t, colors, fx.breathe(3)). Effects run off lights.now,
# the board's clock (the host sets it every frame).
# show() sends only what changed, and dims the whole frame if it would draw more than config.POWER_LIMIT_A.
#
# Where the LEDs are (config.py):
#   BOARD           the island (the bars are the same on both):
#                     "large"   60 LEDs/m, 3 LEDs a hex: rows of 12, 15, 18, 21, 18, 15, 12 LEDs (111)
#                     "small"   144 LEDs/m, 3 LEDs a hex with a line LED on each side: rows of 17, 21, 25, 29,
#                               25, 21, 17 LEDs (155)
#   ISLAND_START    the corner hex where the island's run starts, as seen from seat 1: "G4" (bottom right), "A1"
#                   (top left), "A4" or "G1". Then serpentine: along that row, back along the next, row after row.
#                   From G4: row G right to left, F left to right, ... A; on the small board line G5 comes first.
#   ISLAND_AT       (channel, LED) where the island's run starts
#   BARS_AT         (channel, LED) where each seat's bar starts (LED 1), seats 1-6
#   LED_DRIVER      what drives them (drivers.py)

import config
from . import drivers
from . import geometry as G

SPOTS = G.SPOTS
PER_SPOT = G.LEDS_PER_SPOT
SEATS = G.SEATS
BAR = G.BAR_LEDS
ROW_LENGTHS = G.ROW_LENGTHS
OFF = (0, 0, 0)
BOARDS = ("large", "small")
STARTS = ("G4", "A1", "A4", "G1")


def layout(board, island_at=None, bars_at=None, start=None):
    """For a board ("large" or "small") and placement: (island LEDs on the strip, line LEDs, strand, PHYS).
    strand: LEDs per channel the driver needs (the farthest any part reaches on its channel).
    PHYS[k]: the driver's index for logical LED k. Logical order: spots (37 x 3, in geometry's numbering), then
    bars (6 x 10), then lines (geometry's numbering). island_at, bars_at, start default to config.ISLAND_AT,
    BARS_AT, ISLAND_START."""
    if board not in BOARDS:
        raise ValueError("config.BOARD must be one of %s" % (BOARDS,))
    start = start or getattr(config, "ISLAND_START", STARTS[0])
    if start not in STARTS:
        raise ValueError("config.ISLAND_START must be one of %s" % (STARTS,))
    island_at = island_at or config.ISLAND_AT
    bars_at = bars_at or config.BARS_AT
    lines = board == "small"
    nlines = G.LINES if lines else 0
    island = sum(n * PER_SPOT + (n + 1 if lines else 0) for n in ROW_LENGTHS)
    strand = max([island_at[1] + island] + [at[1] + BAR for at in bars_at])
    phys = [0] * (SPOTS * PER_SPOT + SEATS * BAR + nlines)
    first_line = SPOTS * PER_SPOT + SEATS * BAR
    pos = island_at[0] * strand + island_at[1]
    rows = range(len(ROW_LENGTHS)) if start[0] == "A" else range(len(ROW_LENGTHS) - 1, -1, -1)
    for j, r in enumerate(rows):
        n = ROW_LENGTHS[r]
        # this row's logical LEDs, left to right as seen from seat 1: line 1, hex 1 (3), line 2, ... hex n, line n+1
        run = []
        for c in range(n):
            if lines:
                run.append(first_line + G.LINE_START[r] + c)
            for i in range(PER_SPOT):
                run.append(G.ROWS[r][c] * PER_SPOT + i)
        if lines:
            run.append(first_line + G.LINE_START[r] + n)
        if (j % 2 == 1) == (start[1] == "1"):    # right to left: the first row from a right corner, then every other
            run.reverse()
        for k in run:
            phys[k] = pos
            pos += 1
    for s in range(SEATS):
        b = bars_at[s][0] * strand + bars_at[s][1]
        for i in range(BAR):
            phys[SPOTS * PER_SPOT + s * BAR + i] = b + i
    return island, nlines, strand, phys


def step_brightness(n):
    """Brightness for step n of 1-10 (the USB page's and the radio's slider): a log scale, since eyes see LEDs
    that way. 10 = full, 5 = 10%, each step x1.58: 1.6, 2.5, 4, 6.3, 10, 16, 25, 40, 63, 100%."""
    return 10 ** ((n - 10) / 5)


ISLAND_LEDS, LINES, STRAND, PHYS = layout(config.BOARD)
ISLAND = SPOTS * PER_SPOT                # first logical bar LED
FIRST_LINE = ISLAND + SEATS * BAR
COUNT = FIRST_LINE + LINES               # 171 or 215 logical LEDs
_DARK = bytes(COUNT * 3)
_START_BRIGHTNESS = config.BRIGHTNESS


class Lights:
    def __init__(self, pixels=None):
        """pixels: a pixel object to draw on (drivers.py); by default the one config.LED_DRIVER names."""
        self.raw = bytearray(COUNT * 3)          # what the game drew this frame
        self.sent = bytearray(COUNT * 3)         # what the LEDs show (before dimming)
        self.phys = PHYS
        self.scale = 1.0                         # the power cap's share of the dimming, last frame
        self.level = -1                          # the dimming applied, in 1024ths (brightness x power cap)
        self.brightness = config.BRIGHTNESS      # overall, before the power cap (set_brightness)
        self.now = 0.0                           # the board's clock, for effects; the host sets it every frame
        self.has_lines = LINES > 0
        self.seat_bar = list(range(1, SEATS + 1))   # the bar each seat draws on (carry)
        if pixels is None:
            # The driver always runs at full brightness: show() dims, which saves a whole second copy of the
            # pixels that the LED libraries keep when their own brightness isn't 1.
            pixels = drivers.start(config.LED_DRIVER, config.LED_PIN, STRAND, config.PIXEL_ORDER, 1.0)
        self.pixels = pixels
        if pixels is not None:
            need = max(PHYS) + 1
            if len(pixels) < need:
                raise ValueError("the LED driver has %d LEDs, but ISLAND_AT / BARS_AT reach LED %d"
                                 % (len(pixels), need))
            for i in range(len(pixels)):
                pixels[i] = OFF
            pixels.show()

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
        """Hex t's 3 lights ("B3", or its number): colors is 3 (r, g, b), left to right as seen from seat 1."""
        if not isinstance(t, int):
            t = G.spot(t)
        self._group(t * PER_SPOT, colors, effect, PER_SPOT)

    def bar(self, seat, colors, effect=None):
        """Seat 1-6's bar: colors is 10 (r, g, b), light 0 = LED 1, at that player's left."""
        self._group(ISLAND + (self.seat_bar[seat - 1] - 1) * BAR, colors, effect, BAR)

    def bar_at(self, n, colors, effect=None):
        """Bar n (1-6, its place in config.BARS_AT), whichever seat has it: for drawing by place, like the clock's
        ring."""
        self._group(ISLAND + (n - 1) * BAR, colors, effect, BAR)

    def carry(self, bars):
        """Bars that go with their controllers: {seat: bar} draws that seat on that bar (1-6, its place in
        config.BARS_AT), and the seat whose bar it was on the seat's own. Seats and bars must all differ. Every
        other seat draws on its own bar; {} puts them all back."""
        m = list(range(1, SEATS + 1))
        for s, b in bars.items():
            j = m.index(b)
            m[j], m[s - 1] = m[s - 1], m[j]       # (leaves the seats already placed alone, in any order)
        self.seat_bar = m

    def line(self, k, color, effect=None):
        """Line k's LED ("B1" = row B's left end, or its number). Nothing on the large board."""
        if LINES:
            if not isinstance(k, int):
                k = G.line(k)
            self._set(FIRST_LINE + k, color if effect is None else effect.color(color, self.now))

    def between(self, a, b, color, effect=None):
        """The line LED between hexes a and b, side by side in a row ("B3", "B4": line B4). Nothing on the large
        board."""
        if LINES:
            self.line(G.between(a, b), color, effect)

    def fill(self, c):
        if c == OFF:
            self.raw[:] = _DARK
            return
        for k in range(COUNT):
            self._set(k, c)

    def set_brightness(self, b):
        """Overall brightness from now on, 0..1 (the radio's setting), or None for config.BRIGHTNESS again. The power
        cap still applies on top."""
        self.brightness = _START_BRIGHTNESS if b is None else max(0.0, min(1.0, b))
        config.BRIGHTNESS = self.brightness      # for code that reads it later
        self.level = -1                          # the next show() sends every LED again

    def milliamps(self):
        """Estimated LED current for the frame as drawn, at full scale."""
        return COUNT * config.MA_IDLE + sum(self.raw) * self.brightness * config.MA_PER_CHANNEL / 255

    def show(self):
        limit = config.POWER_LIMIT_A
        scale = 1.0
        if limit:
            ma = self.milliamps()
            budget = limit * 1000
            if ma > budget:
                idle = COUNT * config.MA_IDLE
                scale = max(0.0, (budget - idle) / (ma - idle))
        self.scale = scale
        if self.pixels is None:
            self.sent[:] = self.raw
            return
        level = int(self.brightness * scale * 1024)
        raw = self.raw
        sent = self.sent
        px = self.pixels
        phys = self.phys
        every = level != self.level              # brightness or the power cap changed: every LED again
        self.level = level
        changed = every
        for k in range(COUNT):
            j = k * 3
            if every or raw[j] != sent[j] or raw[j + 1] != sent[j + 1] or raw[j + 2] != sent[j + 2]:
                px[phys[k]] = (raw[j] * level >> 10, raw[j + 1] * level >> 10, raw[j + 2] * level >> 10)
                changed = True
        if changed:
            sent[:] = raw
            px.show()

# Hardware layer for the Adafruit Feather RP2040 SCORPIO: the LED strip and the three inputs.
# It knows nothing about any game: games draw into it through set_spot / set_bar / show, and read
# "move" / "pick" / "back" presses from events().
#
# PLACEHOLDERS (not wired yet; check `import board; print(dir(board))` on the board):
#   PIXEL_PIN       the SCORPIO's level-shifted NeoPixel outputs are named NEOPIXEL0..NEOPIXEL7
#   MOVE/PICK/BACK  any free GPIO; the 3.5 mm switch jacks short the pin to ground (pull-ups on)
# LED order assumed: 3 per spot in spot order (row by row, the engine's numbering), then each player's
# 10-light bar. Change spot_led / bar_led if the strip is laid out differently.

import time

try:
    import board
    import digitalio
    import neopixel
    HARDWARE = True
except ImportError:  # desktop Python: no LEDs, no inputs
    HARDWARE = False

SPOTS = 37
LEDS_PER_SPOT = 3
ISLAND_LEDS = SPOTS * LEDS_PER_SPOT  # 111
BAR_LEDS = 10
PLAYERS = 2
LED_COUNT = ISLAND_LEDS + BAR_LEDS * PLAYERS

PIXEL_PIN_NAME = "NEOPIXEL0"
MOVE_PIN_NAME = "D24"   # placeholder
PICK_PIN_NAME = "D25"   # placeholder
BACK_PIN_NAME = "D4"    # placeholder
BRIGHTNESS = 0.2
DEBOUNCE_S = 0.03


class Board:
    def __init__(self):
        self.pixels = None
        self.inputs = []
        if not HARDWARE:
            return
        pin = getattr(board, PIXEL_PIN_NAME, None) or board.NEOPIXEL
        self.pixels = neopixel.NeoPixel(pin, LED_COUNT, brightness=BRIGHTNESS, auto_write=False)
        for name, event in ((MOVE_PIN_NAME, "move"), (PICK_PIN_NAME, "pick"), (BACK_PIN_NAME, "back")):
            p = getattr(board, name, None)
            if p is None:
                continue
            io = digitalio.DigitalInOut(p)
            io.switch_to_input(pull=digitalio.Pull.UP)
            self.inputs.append([io, event, True, 0.0])   # pin, event, last level, last change time

    # ---- LEDs ----
    @staticmethod
    def spot_led(spot, i):
        return spot * LEDS_PER_SPOT + i

    @staticmethod
    def bar_led(player, i):
        return ISLAND_LEDS + player * BAR_LEDS + i

    def set_spot(self, spot, colors):
        """colors: 3 (r, g, b) tuples, one per light on the spot."""
        if self.pixels is None:
            return
        for i in range(LEDS_PER_SPOT):
            self.pixels[spot * LEDS_PER_SPOT + i] = colors[i]

    def set_bar(self, player, colors):
        """colors: 10 (r, g, b) tuples, light 1 first."""
        if self.pixels is None:
            return
        base = ISLAND_LEDS + player * BAR_LEDS
        for i in range(BAR_LEDS):
            self.pixels[base + i] = colors[i]

    def show(self):
        if self.pixels is not None:
            self.pixels.show()

    def clear(self):
        if self.pixels is not None:
            self.pixels.fill((0, 0, 0))
            self.pixels.show()

    # ---- Inputs ----
    def events(self):
        """Presses since the last call: a list of "move" / "pick" / "back" (on press, debounced)."""
        out = []
        now = time.monotonic()
        for inp in self.inputs:
            level = inp[0].value
            if level != inp[2] and now - inp[3] >= DEBOUNCE_S:
                inp[2] = level
                inp[3] = now
                if not level:          # pulled low = pressed
                    out.append(inp[1])
        return out

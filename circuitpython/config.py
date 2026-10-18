# Board hardware settings. Edit this file to match the wiring; nothing else needs to change.
# See docs/wiring.md (LED channels, seats, free pins) and docs/controllers.md (input types, I2C protocol).
# Drivers, inputs and hubs can be your own: name them "module.Name" (gamehost/plugins.py).

# ---- Which game runs at power-up: games/NAME.py or games/NAME/ (docs/making-games.md) ----
GAME = "salient"              # "paint" is the small example game (and a quick test of every light and controller)
FPS = 40                      # frames a second the host aims for

# ---- LEDs ----
# Which board (docs/wiring.md); the channels, serpentine and bars are the same on both:
#   "large"   60 LEDs/m strip, 3 LEDs on every hex (111)
#   "small"   144 LEDs/m strip, 3 LEDs on every hex plus one under every vertical line: between hexes and at each
#             row's two ends (155; the center row has 29)
BOARD = "large"
# What drives them (gamehost/drivers.py):
#   "neopxl8"   8 outputs at once from LED_PIN on (NEOPIXEL0..7 on the SCORPIO); a channel is one output
#   "neopixel"  one strand on LED_PIN, any board; there's one channel (0), so chain everything on it
#   None        no LEDs
LED_DRIVER = "neopxl8"
LED_PIN = "NEOPIXEL0"
# Where each part starts, as (channel, LED): the island's serpentine (from A1), then each seat's bar (LED 1).
ISLAND_AT = (0, 0)
BARS_AT = ((1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0))     # seats 1..6 (seat 1 = bottom, then clockwise)
# One strand instead (LED_DRIVER = "neopixel"): the island, then the six bars chained after it
#   ISLAND_AT = (0, 0)
#   BARS_AT = ((0, 111), (0, 121), (0, 131), (0, 141), (0, 151), (0, 161))   # 155, 165, ... on the small board
PIXEL_ORDER = "GRB"           # WS2812B; "GRBW" strips aren't supported yet
BRIGHTNESS = 1.0              # overall, before the power limit
POWER_LIMIT_A = 4.0           # the LEDs' share of the 5 V supply; None = no limit (full brightness)
MA_PER_CHANNEL = 20           # current of one color channel of one LED at full
MA_IDLE = 1                   # current of each LED when dark
EFFECT_TIME_SCALE = 1.0       # every light effect's cycle time is multiplied by this (1.5 = all 1.5x slower);
                              # nothing switches lights on and off faster than 3 times a second either way

# ---- Controllers ----
# Each controller is one player's set of inputs. "seat" is where it sits (1-6), or None to choose a side when
# joining; a one-player game always seats its player at the controller's seat (None = seat 1).
# Every input produces some of the actions move, move_back, pick, back, up, down, left, right.
# Input types (any mix, any number per controller; gamehost/inputs.py, or your own as "module.Class"):
#   button   {"type": "button", "pin": "D10", "does": "back"}           optional "hold": "back", "hold_s": 0.8
#   encoder  {"type": "encoder", "a": "D24", "b": "D25"}                 turn = move / move_back; "reverse": True flips
#   scan     {"type": "scan", "pin": "A2", "every": 1.5}                 one switch with auto-scan: the board steps
#                                                                        (move) every `every` s, the switch picks;
#                                                                        optional "hold": "back"
#   ladder   {"type": "ladder", "pin": "A0", "bands": ((0.0, 0.5, "move"), (1.0, 1.5, "pick"), (2.0, 2.5, "back"))}
#            several switches on one analog pin through resistors; bands are volts, nothing pressed = none
# Switches short the pin to ground (pull-ups on). An encoder's two pins must be consecutive GPIOs.
CONTROLLERS = [
    # The default wired controller: a rotary encoder (turn = move, push = pick) and one button (back).
    {"name": "wired", "seat": 1, "inputs": [
        {"type": "encoder", "a": "D24", "b": "D25"},
        {"type": "button", "pin": "D9", "does": "pick"},
        {"type": "button", "pin": "D10", "does": "back"},
    ]},
    # Examples:
    # {"name": "three buttons", "seat": 4, "inputs": [
    #     {"type": "button", "pin": "D5", "does": "move"},
    #     {"type": "button", "pin": "D6", "does": "pick"},
    #     {"type": "button", "pin": "D11", "does": "back"}]},
    # {"name": "one switch", "seat": 2, "inputs": [{"type": "scan", "pin": "A2", "every": 1.5, "hold": "back"}]},
    # {"name": "d-pad", "seat": None, "inputs": [
    #     {"type": "button", "pin": "A0", "does": "up"}, {"type": "button", "pin": "A1", "does": "down"},
    #     {"type": "button", "pin": "A2", "does": "left"}, {"type": "button", "pin": "A3", "does": "right"},
    #     {"type": "button", "pin": "D11", "does": "pick"}, {"type": "button", "pin": "D12", "does": "back"}]},
]

# Hubs: sources that bring their own controllers (gamehost/hubs.py). Take one out to turn it off.
#   "i2c"       outboard controller boards on the STEMMA QT I2C bus (docs/controllers.md). Each gamepad or switch box
#               on them becomes its own controller (seat None) the first time it sends something.
#   "console"   the USB serial console as up to 6 controllers, for testing: type m (move), n (move back), p (pick),
#               b (back), w/a/s/d (up/left/down/right); a digit 1-6 switches which console controller the keys go to.
CONTROLLER_HUBS = ("i2c", "console")
I2C_ADDRESSES = range(0x30, 0x40)   # where to look for controller boards
I2C_FREQUENCY = 100000
I2C_RESCAN_S = 5                     # how often to look for boards plugged in later

# Board hardware settings. Edit this file to match the wiring; nothing else needs to change.
# See docs/wiring.md (LED channels, seats, free pins) and docs/controllers.md (input types, I2C protocol).

# ---- Which game runs at power-up (a module with a Game class; see README.md) ----
GAME = "salient_game"
FPS = 40                      # frames a second the host aims for

# ---- LEDs ----
# The island's LED map (docs/wiring.md); the channels, serpentine and bars are the same on both:
#   "60_leds_per_meter"   3 LEDs on every spot (111)
#   "144_leds_per_meter"  3 LEDs on every spot plus one under every vertical line between spots and at each row's
#                         ends: line, spot, line, spot, ... line (155; the center row has 29)
LED_MAP = "60_leds_per_meter"
LED_FIRST_PIN = "NEOPIXEL0"   # NeoPXL8 drives 8 consecutive outputs starting here (NEOPIXEL0..7 on the SCORPIO)
ISLAND_CHANNEL = 0            # 111 LEDs, serpentine from A1
BAR_CHANNELS = (1, 2, 3, 4, 5, 6)   # the bar for seats 1..6 (seat 1 = bottom, then clockwise)
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
# Input types (any mix, any number per controller):
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

# Outboard controller boards on the STEMMA QT I2C bus (docs/controllers.md). Each gamepad or switch box on them
# becomes its own controller (seat None) the first time it sends something.
I2C_CONTROLLERS = True
I2C_ADDRESSES = range(0x30, 0x40)   # where to look for them
I2C_FREQUENCY = 100000
I2C_RESCAN_S = 5                     # how often to look for boards plugged in later

# The USB serial console as up to 6 controllers, for testing: type m (move), n (move back), p (pick), b (back),
# w/a/s/d (up/left/down/right); a digit 1-6 switches which console controller the following keys belong to.
SERIAL_CONTROLLER = True

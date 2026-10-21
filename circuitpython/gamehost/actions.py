# The actions a controller sends. Every input device, whatever it is, is turned into these, and they're all a game
# ever sees: it never knows whether a "pick" came from a big button, a switch on a head rest, a gamepad or a pedal.
#
# Actions are plain strings, so `action == "pick"` works; these names are here for code that prefers constants.
#
#   move        step forward through what can be picked (a button, an encoder turned clockwise, a scan tick)
#   move_back   step backward (an encoder turned the other way)
#   pick        choose what the cursor is on
#   back        go back / cancel
#   up, down, left, right   a D-pad or joystick: move the cursor directly
#   menu        back to the game picker, from any game: a wired button held MENU_HOLD_S (config.py), a console's q,
#               the USB page's Menu. The board handles it (it asks first: pick the red light on your bar); a game
#               never sees it
#
# Not every controller has every action. A single switch has only move (the board scans for it) and pick, so a game
# must offer another way to do anything it would normally put on back. Controller.can says what a controller has.

MOVE = "move"
MOVE_BACK = "move_back"
PICK = "pick"
BACK = "back"
UP = "up"
DOWN = "down"
LEFT = "left"
RIGHT = "right"
MENU = "menu"

ALL = (MOVE, MOVE_BACK, PICK, BACK, UP, DOWN, LEFT, RIGHT, MENU)
ARROWS = (UP, DOWN, LEFT, RIGHT)
ONE_SWITCH = (MOVE, PICK)          # the least a controller can have

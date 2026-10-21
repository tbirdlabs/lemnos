# The interface between the board and a game. A game subclasses Game and fills in what it needs; the host
# (host.py) calls it. The game never touches pins, LED strips or devices, and the host knows nothing about the game.
#
#   from gamehost.game import Game as Base
#
#   class Game(Base):
#       def event(self, controller, action, now): ...    # a player pressed something
#       def update(self, now): ...                        # timers, animations, computer players
#       def draw(self, lights, now): ...                  # light the board for this frame
#
# Every frame (config.FPS, 40 a second by default) the host:
#   1. tells the game about controllers that arrived or left   controller_added / controller_removed
#   2. hands it every action since the last frame, in order    event
#   3. passes on lines typed on the serial console             command
#   4. lets it run its clock                                   update
#   5. clears the lights, has the game draw, and shows them    draw
# `now` is the board's clock in seconds (time.monotonic()); use it rather than reading the time yourself, so tests can
# run a game on a fake clock.
#
# What a game gets (the Board, as self.board):
#   board.lights        lights.Lights: spot(t, colors), bar(seat, colors), line(row, k, color), with effects (fx.py)
#   board.controls      controls.Controls; board.controllers is the list of controllers connected right now
#   board.seats         6
# and, to import as it likes: geometry (spots, neighbors, sides, each seat's view), fx (light effects), dice (a die
# roll shown on a bar), actions (the action names), walltime (the time of day). See docs/making-games.md.


class Game:
    """Base class for a game on the board. Every method has a do-nothing default, so override only what you use."""

    def __init__(self, board):
        """Set up. board: the host's Board (lights, controls, seats). Nothing is drawn until the first draw()."""
        self.board = board

    def event(self, controller, action, now):
        """One action from one controller.

        controller  a controls.Controller: .name, .seat (1-6, or None if it hasn't one), .can (the set of actions
                    it can send). The same object every time for the same controller, so it can be used as a key.
        action      one of actions.ALL: "move", "move_back", "pick", "back", "up", "down", "left", "right".
        """

    # The console commands command() takes, for the console's "help": (command, what it does) pairs, such as
    # ("time 14:32", "set the clock"). Leave it empty if the game has none.
    HELP = ()

    def command(self, text, now):
        """A command line typed on the serial console (or sent by a tool), such as "time 14:32" for the clock.
        Return the reply to print, or None if the game has no such command (the host says so). List them in HELP."""
        return None

    def update(self, now):
        """Called once a frame after the events: run timers and animations, let computer players think.
        Keep each call short (well under a frame) so the lights stay smooth; spread long work over several frames."""

    def draw(self, lights, now):
        """Draw the whole frame. The host has already set every light dark, and shows the frame afterward, so just
        set the lights that should be lit. Don't change the game here; it may be skipped or called more than once."""

    def controller_added(self, controller, now):
        """A controller appeared: every wired one at power-up, and an I2C gamepad or console controller the first
        time it's used (or when it comes back after controller_removed)."""

    def controller_removed(self, controller, now):
        """A controller went away (an I2C gamepad disconnected). It sends nothing until controller_added again.
        A game might let the computer take over that player, or pause."""

    # ---- Optional: setting up a game from the USB page (Salient.html) instead of on the board ----
    # The page shows options() as a form with a Start button, and calls setup() with what was chosen. Its New game
    # button needs nothing from the game: the host makes the game afresh, so it's back at its own setup on the board.

    def options(self):
        """The fields of the page's setup form, as a list of dicts:
            key       the field's name in setup()'s choices
            label     what people see
            choices   [(value, label), ...]; values are strings. Controllers can be choices too (their .id as the
                      value): the page asks again whenever controllers come or go
            value     the one chosen to begin with
            show      optional {key: [values]}: show the field only while those fields have one of those values
            note      optional: a line under the field
        [] (the default): the game has no setup form; the page offers only New game."""
        return []

    def setup(self, choices, now):
        """Start a game as set up on the page. choices: {key: value} for each field options() gave (strings).
        Return None if it started, or a message to show on the page if it can't (it's changed nothing then)."""
        return "This game has no setup here."

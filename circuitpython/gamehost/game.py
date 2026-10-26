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
# A game with a setup (options() below) is set up on the board by the host's lobby (lobby.py), the same way for every
# game: choosing the game, joining, its fields, starting, and after the game playing again or going back. The game
# only lists its fields, starts from what was chosen (setup), may draw a preview of the choices, and says when a game
# is over (finished). A game with no setup just runs, from when it's made.
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

    # ---- Optional: a setup, on the board (the lobby) and on the USB page (Lemnos.html) ----
    # The lobby walks people through options() on the board; the page shows it as a form with a Start button. Both
    # call setup() with what was chosen. Until then the game is idle (the lobby draws, with preview()); once
    # finished() says it's over, the lobby has the controllers again: pick plays again (setup() with the same
    # choices), back returns to the setup. The page's New game makes the game afresh, back at its setup.

    def options(self, choices=None):
        """The setup's fields, as a list of dicts:
            key       the field's name in setup()'s choices
            label     what people see
            choices   [(value, label), ...]; values are strings. A third item, a color (r, g, b), is how the board
                      shows that choice on a bar. Controllers can be choices too (their .id as the value): the page
                      asks again whenever controllers come or go
            value     the one chosen to begin with
            show      optional {key: [values]}: (the page) show the field only while those fields have one of those
                      values
            note      optional: a line under the field (the page)
          and for the board's lobby:
            player    a controller's id: this field is that player's own (their seat, color, side...), set by them
                      on their own bar after they join. Give each connected controller its own copy (key "seat:" +
                      its id, say)
            out       (a player's field) its value for "not playing"; a player who hasn't joined has it
            unique    (a player's field) a name: no two players have the same value in fields of that name
            seat      (a player's field) True: its value is the seat (1-6) where that player's bar is
            bar       "fill": the bar lights as many as the value (how many, a level), not a light per choice
            color     the bar's color for a "fill" field (default white)
            board     False: not shown on the board; its value is whatever options() gives (worked out from the
                      other choices)
        choices: what's chosen so far on the board ({key: value}), so the form can follow it (fewer players to
        choose from once more have joined, a field that only matters for one human); None from the page.
        [] (the default): the game has no setup; it runs as soon as it's made, and the page offers only New game."""
        return []

    def setup(self, choices, now):
        """Start a game as set up on the board or the page. choices: {key: value} for each field options() gave
        (strings). Return None if it started, or a message saying why it can't (it's changed nothing then)."""
        return "This game has no setup here."

    def preview(self, lights, now, lobby):
        """Draw the setup screen as chosen so far (the lobby draws the bars of players setting a field over it).
        lobby.choices ({key: value}), lobby.joined (controllers, the leader first), lobby.editing(controller) (the
        key it's setting, "start", or None when it's done or not joined)."""

    def finished(self):
        """True once a game is over and its last picture is up (any last rolls shown): the lobby takes over."""
        return False

# The game host: runs one game on the board. It owns the lights and the controllers; the game owns everything else.
# The interface a game sees is in game.py; how a game is found is load_game() below. Between games (choosing one,
# joining, its setup, play again) the host's lobby (lobby.py) has the controllers and the lights.
#
#   from gamehost import host
#   host.run()                  # the game config.GAME names, forever (code.py does this at power-up)
#   host.run("paint")           # another one
#
# Nothing in the host changes for a new game, a new input device or a new LED driver.
# Settings can also arrive while it runs, from the USB page or the radio's web page (Controls.settings):
# "brightness" (1-10 on a log scale, lights.step_brightness: 5 = 10%; or "default" for config.BRIGHTNESS) and "game"
# (switch to another game now, and start with it at power-up; "default" for config.GAME). Both are remembered
# through power-off (saved.py).

import gc
import sys
import time
import config
from . import geometry
from . import saved
from .controls import Controls, ADDED, REMOVED
from .lights import Lights, OFF, step_brightness
from .lobby import Lobby


class Board:
    """What a game is given (as Game.board).

    lights        lights.Lights: draw with spot(), bar(), line()
    controls      controls.Controls
    controllers   the controllers connected right now (controls.Controller)
    seats         6, numbered 1-6 clockwise from the bottom
    """

    def __init__(self, lights=None, controls=None):
        """lights, controls: made from config.py unless given (tests pass in their own)."""
        self.lights = lights if lights is not None else Lights()
        self.controls = controls if controls is not None else Controls()
        self.seats = geometry.SEATS

    @property
    def controllers(self):
        return self.controls.connected()


def _module_path(name):
    return name if "." in name else "games." + name


def unload_game(name):
    """Forget the modules of the game called `name` (games.NAME and everything under it), so the memory its code
    took comes back once nothing uses it. Loading it again reads it afresh."""
    path = _module_path(name)
    for k in list(sys.modules):
        if k == path or k.startswith(path + "."):
            del sys.modules[k]
    if "." in path:
        parent, leaf = path.rsplit(".", 1)
        pm = sys.modules.get(parent)
        if pm is not None and hasattr(pm, leaf):
            try:
                delattr(pm, leaf)        # the package holds its submodules too
            except (AttributeError, TypeError):
                pass


def load_game(name=None):
    """The Game class of the game called `name` (default config.GAME): the file games/NAME.py, or the folder
    games/NAME/ with the Game class in its game.py. A name with a dot in it ("mygames.chess") is imported as it is."""
    name = name or config.GAME
    path = _module_path(name)
    mod = __import__(path, None, None, ["Game"])
    if not hasattr(mod, "Game"):
        mod = __import__(path + ".game", None, None, ["Game"])
    return mod.Game


def game_names():
    """The games on the board, sorted: each games/NAME.py (or .mpy) and games/NAME/ folder with a game.py in it."""
    import os
    import games
    folder = games.__file__.replace("\\", "/").rsplit("/", 1)[0]
    names = set()
    for n in os.listdir(folder):
        if n[0] in "_.":
            continue
        if n.endswith(".py") or n.endswith(".mpy"):
            names.add(n.rsplit(".", 1)[0])
            continue
        try:
            inside = os.listdir(folder + "/" + n)
        except OSError:
            continue                     # a file of another kind
        if "game.py" in inside or "game.mpy" in inside:
            names.add(n)
    return sorted(names)


def _game_name(cls):
    """"paint" for games.paint.Game, "salient" for games.salient.game.Game ("" where classes have no __module__)."""
    parts = getattr(cls, "__module__", "").split(".")
    return parts[-2] if parts[-1] == "game" and len(parts) > 1 else parts[-1]


class Host:
    """One game on one board. frame(now) is one pass of the loop; run() calls it config.FPS times a second."""

    def __init__(self, game_class=None, board=None, name=None):
        """name: the game's name, as the radio shows it (default config.GAME if game_class isn't given)."""
        self.board = board if board is not None else Board()
        self.game = (game_class or load_game(name))(self.board)
        self.name = name or (config.GAME if game_class is None else _game_name(game_class))
        self.board.controls.game = self.name
        self.board.controls.current = self.game
        self.board.controls.brightness = "default"
        self.lobby = Lobby(self)

    def switch(self, name, now):
        """Run another game from now on (the game setting). The controllers connected are handed to it. True if
        that game is running now; False if there's no such game, or it fails to start (the old one carries on).
        Memory gets broken up as games come and go, so a big game (Salient) may not fit again in what's left: then the
        board's program starts afresh with it (restart(), a few seconds), as at power-up. The saved game setting
        (saved.py) says which game that is, so apply() saves it before switching. The radio and the USB page hand the
        controllers and settings back when they hear the board again."""
        if name == self.name:
            return True
        if "." not in name and name not in game_names():
            return False
        old = self.name
        # The old game's memory back first, code and all, so any number of games can take turns. (A game class
        # given in code rather than found in games/ can't be loaded again by name: that one is kept.)
        keep = None if _module_path(old) in sys.modules else type(self.game)
        self.game = None
        self.board.controls.current = None
        unload_game(old)
        gc.collect()
        try:
            self._start(load_game(name), name, now)
        except MemoryError:
            print("%s doesn't fit in the memory left: starting afresh with it." % name)
            self.restart()
        except Exception as e:           # a bug in it: the old one again, afresh
            print("Game \"%s\" doesn't start (%r)." % (name, e))
            self.game = None
            unload_game(name)
            gc.collect()
            try:
                self._start(keep or load_game(old), old, now)
            except MemoryError:
                self.restart()
            return False
        print("Now playing %s." % name)
        return True

    def restart(self):
        """The board's program from the start (CircuitPython's soft reload, as Ctrl-D: the USB connection stays up).
        Off the board there's no such thing: MemoryError."""
        try:
            import supervisor
        except ImportError:
            raise MemoryError("no room for the game")
        supervisor.reload()

    def new_game(self, now):
        """The game running, made afresh (the USB page's New game): back at its setup on the board."""
        cls = type(self.game)
        self.game = None                 # the old one's memory back before the new one is made
        self.board.controls.current = None
        gc.collect()
        try:
            self._start(cls, self.name, now)
        except MemoryError:
            self.restart()

    def _start(self, cls, name, now):
        self.game = cls(self.board)
        self.name = name
        self.board.controls.game = name
        self.board.controls.current = self.game
        for c in self.board.controllers:
            self.game.controller_added(c, now)
        self.lobby.reset()

    def apply(self, key, value, now, save=True):
        """A setting from a hub (the USB page, the radio): brightness and game are remembered through power-off
        (saved.py) unless save is False. "new_game" and "setup" (from the USB page) start a game. Unknown ones are
        ignored: a newer radio may send more. Returns None, or a message saying why it didn't happen."""
        if key == "new_game":
            self.new_game(now)
            return None
        if key == "setup":
            try:
                msg = self.game.setup(value, now)
            except Exception as e:       # a game's bug shouldn't stop the board
                print("%s: setup failed: %r" % (self.name, e))
                return "The game couldn't start (%s)." % e
            if msg is None:
                self.lobby.started(value)
            return msg
        if key == "brightness":
            if value == "default":
                self.board.lights.set_brightness(None)
            elif value.isdigit() and 1 <= int(value) <= 10:
                self.board.lights.set_brightness(step_brightness(int(value)))
            else:
                return "Brightness is 1 to 10."
            self.board.controls.brightness = value
        elif key == "game":
            name = config.GAME if value == "default" else value
            before = saved.get("game")
            if save:
                saved.put("game", None if value == "default" else value)     # first: switch() may restart with it
            if not self.switch(name, now):
                saved.put("game", before)
                return "There's no game called %s." % value
            return None
        else:
            return None
        if save:
            saved.put(key, value if value != "default" else None)

    HELP = (("help", "this list"), ("mem", "free RAM"))

    def command(self, text):
        """The host's own console commands (HELP), answered before the hubs' and the game's."""
        word = text.strip().lower()
        if word == "mem":
            gc.collect()
            free = gc.mem_free() if hasattr(gc, "mem_free") else 0
            used = gc.mem_alloc() if hasattr(gc, "mem_alloc") else 0
            return "RAM: %d bytes free, %d in use (%s)." % (free, used, self.name)
        if word in ("help", "?"):
            return self.help()
        return None

    def help(self):
        """Every console command there is right now: the host's, each hub's and the running game's (their HELP),
        then the console's keys."""
        groups = [("Board", self.HELP)]
        for h in self.board.controls.hubs:
            if getattr(h, "HELP", None):
                label = getattr(h, "LABEL", type(h).__name__)
                groups.append((label[:1].upper() + label[1:], h.HELP))   # (MicroPython has no str.capitalize)
        groups.append((self.name, getattr(self.game, "HELP", ()) or (("", "no commands"),)))
        from .hubs import CONSOLE_KEYS
        # a command starting with a key letter has to be typed with a / in front, or its first letter is a key
        groups = [(t, [("/" + c if c[:1].lower() in CONSOLE_KEYS else c, w) for c, w in cmds]) for t, cmds in groups]
        width = max(len(c) for _, cmds in groups for c, _ in cmds) + 2
        out = []
        for title, cmds in groups:
            out.append(title + ":")
            for c, what in cmds:
                out.append("  " + c + " " * (width - len(c)) + what if c else "  " + what)
        out.append("Keys: m move, n move back, p pick, b back, w a s d up left down right, q menu (the game picker); "
                   "1-6 which console controller.")
        out.append("A command starting with one of those letters needs a / in front (the USB page adds it).")
        return "\n".join(out)

    def restore(self, now=0.0):
        """The saved brightness (the saved game is run() choosing what to start)."""
        b = saved.get("brightness")
        if b:
            self.apply("brightness", b, now, save=False)

    def frame(self, now):
        board = self.board
        events = board.controls.stream(now)          # arrivals, departures and actions, in order
        for key, value, reply in board.controls.take_settings():
            msg = self.apply(key, value, now)        # (a new game is handed the controllers connected now)
            if reply is not None:
                reply(msg)
        lobby = self.lobby               # (self.game, not a copy: picking a game in the lobby switches it)
        for kind, c, a in events:
            if kind == ADDED:
                self.game.controller_added(c, now)
                lobby.controller_added(c, now)
            elif kind == REMOVED:
                self.game.controller_removed(c, now)
                lobby.controller_removed(c, now)
            else:
                lobby.event(c, a, now)   # the game's, while it's being played
        for text in board.controls.take_commands():
            reply = self.command(text)
            if reply is None:
                reply = board.controls.hub_command(text)
            if reply is None:
                reply = self.game.command(text, now)
            print(reply if reply is not None else "No command \"%s\" in this game." % text)
        if not lobby.paused:
            self.game.update(now)
        lobby.update(now)
        lights = board.lights
        lights.fill(OFF)
        lights.now = now
        self.lobby.draw(lights, now)
        lights.show()
        board.controls.shown(lights, now)


def starting_game(game=None):
    """(name, Game class) of the game to start: `game` if given, else the one last picked on the USB page or the
    radio's web page (saved.py), else config.GAME; config.GAME too if that one won't load."""
    name = game or saved.get("game") or config.GAME
    try:
        return name, load_game(name)
    except Exception as e:
        print("Game \"%s\" doesn't load (%r); starting %s." % (name, e, config.GAME))
        if game is None and saved.get("game") == name:
            saved.put("game", None)      # so it isn't tried at every power-up
        gc.collect()
        return config.GAME, load_game(config.GAME)


def run(game=None):
    """Run a game until power-off: `game`, or the one starting_game() picks."""
    name, cls = starting_game(game)
    try:
        h = Host(cls, name=name)
    except MemoryError:
        if game is None and saved.get("game") == name and name != config.GAME:
            # a saved game that doesn't fit would stop the board at every power-up: forget it, start again
            print("Game \"%s\" doesn't fit in memory; starting %s instead." % (name, config.GAME))
            saved.put("game", None)
            import supervisor
            supervisor.reload()
        raise
    h.restore()
    period = 1.0 / config.FPS
    while True:
        now = time.monotonic()
        h.frame(now)
        left = period - (time.monotonic() - now)
        if left > 0:
            time.sleep(left)

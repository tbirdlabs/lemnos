# Controllers: one per player's set of inputs, whatever they are. This turns the wired inputs (inputs.py, listed in
# config.CONTROLLERS) and the hubs (hubs.py: I2C controller boards, the serial console) into (controller, action)
# pairs. Games never see pins or devices, only Controller objects and actions (actions.py):
#   move, move_back, pick, back, up, down, left, right
# A Controller has .id, .name, .seat (1-6 or None) and .can (the set of actions it can send), so a game can tell,
# for example, that a one-switch controller has no back and offer a "way out" stop instead.

import time
import config
from . import actions as A
from . import plugins
from .inputs import INPUTS
from .hubs import HUBS

ACTIONS = A.ALL
ALL = A.ALL


class Controller:
    """One player's controller, as a game sees it.

    id          unique and stable ("wired0", "i2c-30-1", "console2")
    name        for people: the name in config.py, or "pad 1 on 0x30"
    seat        the seat it sits at (1-6), or None if its player chooses one in the game
    can         the set of actions it can send (actions.py); may change, e.g. when an I2C pad says it's one switch
    connected   False after it went away (Game.controller_removed) until it sends again
    bar         the bar it carries (1-6, its place in config.BARS_AT), or None: the bar goes where its player sits
                (the lobby sets lights.carry), so it always shows that player's own lights
    """

    def __init__(self, cid, name, seat, can):
        self.id = cid
        self.name = name
        self.seat = seat
        self.can = set(can)
        self.connected = True
        self.bar = None

    def __repr__(self):
        return "<%s seat %s>" % (self.name, self.seat)


def wired_bar(k, spec):
    """The bar wired controller k (its place in config.CONTROLLERS) carries: its "bar", or by default bar 1 for the
    first and none for the rest."""
    return spec.get("bar", 1 if k == 0 else None)


ADDED = "added"
REMOVED = "removed"
ACTION = "action"


class Controls:
    """Every controller on the board. The host calls poll() each frame; a game reads .controllers if it likes."""

    def __init__(self, hardware=None):
        """hardware: set up the inputs and hubs in config.py (default: if this is a CircuitPython board).
        Without them (desktop tests), only feed() produces actions."""
        if hardware is None:
            try:
                import board
                hardware = True
            except ImportError:
                hardware = False
        self.controllers = []
        self.sources = []          # (input, controller)
        self.hubs = []
        self.queue = []
        self.notices = []          # (ADDED or REMOVED, controller), for the host to pass to the game
        self.commands = []         # typed command lines, for the host to pass to the game
        self.settings = []         # (key, value, reply) from a hub (SET lines), for the host to apply
        self.current = None        # the Game object running (the host sets it; the USB page asks it for options())
        self.game = ""             # the name of the game running (the host sets it; the radio reports it)
        self.brightness = "default"   # the brightness setting, "1".."10" or "default" (the host sets it)
        self._stream = None        # while stream() polls: where arrivals and departures go, in order with actions
        if not hardware:
            return
        for k, spec in enumerate(config.CONTROLLERS):
            c = self.get("wired%d" % k, spec.get("name", "wired %d" % (k + 1)), spec.get("seat"), ())
            c.bar = wired_bar(k, spec)
            for inp in spec["inputs"]:
                try:
                    src = plugins.find(inp["type"], INPUTS, "input type")(inp)
                except Exception as e:          # a missing pin or library shouldn't stop the board
                    print("controller %s: %s input not set up: %s" % (c.name, inp.get("type"), e))
                    continue
                c.can |= src.can
                self.sources.append((src, c))
        for name in config.CONTROLLER_HUBS:
            try:
                self.hubs.append(plugins.find(name, HUBS, "controller hub")(self))
            except Exception as e:
                print("controller hub %s not set up: %s" % (name, e))

    def find(self, cid):
        """The controller with this id, or None if there's none yet."""
        for c in self.controllers:
            if c.id == cid:
                return c
        return None

    def get(self, cid, name, seat, can):
        """The controller with this id, made on first use (and reconnected if it had gone away)."""
        c = self.find(cid)
        if c is not None:
            if not c.connected:
                c.connected = True
                self._notice(ADDED, c)
            return c
        c = Controller(cid, name, seat, can)
        self.controllers.append(c)
        self._notice(ADDED, c)
        return c

    def remove(self, controller):
        """The controller went away (a hub calls this). It stays in the list, marked not connected."""
        if controller.connected:
            controller.connected = False
            self._notice(REMOVED, controller)

    def _notice(self, kind, c):
        if self._stream is not None:
            self._stream.append((kind, c, None))
        else:
            self.notices.append((kind, c))

    def connected(self):
        """The controllers connected right now."""
        return [c for c in self.controllers if c.connected]

    def feed(self, controller, action):
        """Queue an action as if the controller had sent it (desktop tests, other code)."""
        self.queue.append((controller, action))

    def command(self, text):
        """Queue a command line for the game (the console hub calls this; desktop tests too)."""
        self.commands.append(text)

    def setting(self, key, value, reply=None):
        """Queue a board setting for the host (the radio and the USB page call this): "brightness" 1-10 or
        "default", "game", and from the USB page "setup" ({key: value}, for Game.setup) and "new_game".
        reply(message): called once it's done, with None or what went wrong."""
        self.settings.append((key, value, reply))

    def take_settings(self):
        """Settings since the last call, oldest first: [(key, value, reply), ...]."""
        out = self.settings
        self.settings = []
        return out

    def hub_command(self, text):
        """A console command for a hub ("radio pair"): its reply, or None if no hub takes it."""
        for h in self.hubs:
            if hasattr(h, "command"):
                reply = h.command(text)
                if reply is not None:
                    return reply
        return None

    def shown(self, lights, now):
        """The frame just went to the LEDs: hubs that want it (the USB page's board view) get it."""
        for h in self.hubs:
            if hasattr(h, "shown"):
                h.shown(lights, now)

    def take_commands(self):
        """Command lines typed since the last call, oldest first."""
        out = self.commands
        self.commands = []
        return out

    def take_notices(self):
        """Controllers added or removed since the last call: [(ADDED or REMOVED, controller), ...]."""
        out = self.notices
        self.notices = []
        return out

    def stream(self, now=None):
        """Everything since the last call, in the order it happened: (ADDED, controller, None),
        (REMOVED, controller, None) and (ACTION, controller, action). So a controller that arrives and presses
        something in the same frame arrives first, and one that presses and leaves leaves last. (The host uses this;
        take_notices() and poll() are the same split in two.)"""
        if now is None:
            now = time.monotonic()
        out = [(k, c, None) for k, c in self.notices]
        self.notices = []
        out.extend((ACTION, c, a) for c, a in self.queue)
        self.queue = []
        self._stream = out
        try:
            for src, c in self.sources:
                src.poll(now, lambda a, c=c: out.append((ACTION, c, a)))
            for h in self.hubs:
                h.poll(now, lambda c, a: out.append((ACTION, c, a)))
        finally:
            self._stream = None
        return out

    def poll(self, now=None):
        """Every (controller, action) since the last call, oldest first."""
        if now is None:
            now = time.monotonic()
        out = self.queue
        self.queue = []
        for src, c in self.sources:
            src.poll(now, lambda a, c=c: out.append((c, a)))
        for h in self.hubs:
            h.poll(now, lambda c, a: out.append((c, a)))
        return out

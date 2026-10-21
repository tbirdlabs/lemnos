# The USB page: Salient.html on the CIRCUITPY drive, opened in Edge, Chrome or Firefox on the computer the board is
# plugged into. Settings, an on-screen controller, the board's lights live, the time from the computer and the
# console, over the USB serial console (Web Serial), with nothing to install.
# It shares the console with people typing (hubs.Console): a line from the page starts with "!" and every line the
# board sends it starts with "@", so a terminal only sees them after it types "!HELLO" itself.
#
# From the page: link.py's IN, SET, TIME and HELLO, and
#   !HELLO page 1         the page connected (or reconnected); the board answers with everything below
#   !WATCH on|off         send the lights (LEDS), or stop
#   !BYE                  the page is closing: its players leave (closing the port does the same)
#   !START {"mode": "invasion", ...}       start a game set up on the page (Game.setup); answered with SETUP
#   !NEWGAME              the game running, made afresh: back at its setup on the board; answered with SETUP
# To the page:
#   @HELLO 2026.10.20     the board software (gamehost.VERSION)
#   @BOARD large 171      config.BOARD and the LED count: 37 x 3 on the hexes, 6 x 10 on the bars, (small) 44 lines
#   @GAMES clock paint salient testpattern
#   @STATE default_game salient            config.GAME, the game "SET game default" goes back to
#   @STATE default_brightness 0.05         config.BRIGHTNESS (0-1), what "SET brightness default" goes back to
#   @STATE game salient                    the game running, whenever it changes
#   @STATE brightness 6                    1-10 or "default", whenever it changes
#   @PLAYERS [{"id": "wired0", "name": "wired", "seat": 1}, ...]   the controllers connected, when that changes
#   @LEDS <base64>        every LED's (r, g, b) in lights.py's logical order, as the game drew it (before brightness
#                         and the power cap), when it changes, at most WATCH_FPS times a second
#   @OPTIONS [{"key": "mode", "label": "Game", "choices": [["invasion", "Invasion"], ...], "value": "invasion"}, ...]
#                         the game's setup form (Game.options()), when it changes (another game, controllers)
#   @SETUP ok  /  @SETUP <why not>         the answer to START or NEWGAME
#   @ACK brightness       a SET arrived
# The page's players are the controllers usb-p1..usb-p6 ("player 1 (USB)"); they choose their side in the game.

import binascii
import json
import config
from .link import Link, version

WATCH_FPS = 15
PLAYERS_EVERY_S = 0.5


class Page(Link):
    ID = "usb"
    LABEL = "USB"
    MAX_LINE = 1200                     # a setup (START) can run long

    def __init__(self, controls, write=print, out=None):
        """write(text): one line to the computer (print, on the board). out(bytes): writes bytes straight to the
        same place (usb_cdc.console.write on the board), for the lights; None: they go through write()."""
        Link.__init__(self, controls)
        self.write = write
        self.out = out
        self.active = False             # the page has said HELLO and is still there
        self.watch = False
        self.last = None                # the lights last sent (a bytearray, reused)
        self.next_frame = 0.0
        self.told = {}
        self.players = None
        self.next_players = 0.0
        self.options = None             # the form last sent (JSON), or None: work it out again
        self.options_of = None          # the game object it was for

    def send(self, text):
        self.write("@" + text)

    def hello(self, words):
        from . import host
        from . import lights
        self.version = words[1] if len(words) > 1 else "?"
        self.active = True
        self.told = {}
        self.players = None
        self.next_players = 0.0
        self.options = None
        self.last = None
        self.send("HELLO " + version())
        self.send("BOARD %s %d" % (config.BOARD, lights.COUNT))
        self.send("GAMES " + " ".join(host.game_names()))
        self.send("STATE default_game " + config.GAME)
        self.send("STATE default_brightness %g" % lights._START_BRIGHTNESS)

    def line(self, raw, now, emit):
        if raw.startswith("START "):
            try:
                choices = json.loads(raw[6:])
            except (ValueError, MemoryError):
                choices = None
            if isinstance(choices, dict):
                self.controls.setting("setup", {str(k): str(v) for k, v in choices.items()}, self.answer)
            else:
                self.answer("The setup didn't arrive whole; try again.")
            return
        if raw.strip() == "NEWGAME":
            self.controls.setting("new_game", "", self.answer)
            return
        words = Link.line(self, raw, now, emit)
        if not words:
            return
        if words[0] == "WATCH":
            self.watch = self.active and (len(words) < 2 or words[1] != "off")
            self.last = None
        elif words[0] == "BYE":
            self.closed()

    def answer(self, message):
        """The host's answer to START or NEWGAME: None if the game started."""
        if self.active:
            self.send("SETUP " + ("ok" if message is None else message))
            self.options = None           # its form may have changed too (the difficulty, a new game object)
            self.next_players = 0.0

    def closed(self):
        """The page went away: no more lines to it, and its players leave."""
        if self.active:
            self.active = False
            self.watch = False
            self.last = None
            self.drop_all()

    def poll(self, now):
        """Every frame: tell the page what changed. Short of memory, a message waits for the next try: the page is
        never worth stopping the board for."""
        if not self.active:
            return
        try:
            self._poll(now)
        except MemoryError:
            self.next_players = now + PLAYERS_EVERY_S

    def _poll(self, now):
        c = self.controls
        for key in ("game", "brightness"):
            v = getattr(c, key)
            if self.told.get(key) != v:
                self.send("STATE %s %s" % (key, v))
                self.told[key] = v
        if now < self.next_players:
            return
        self.next_players = now + PLAYERS_EVERY_S
        p = [(x.id, x.name, x.seat) for x in c.connected()]
        if p != self.players:
            self.send("PLAYERS " + json.dumps([{"id": i, "name": n, "seat": s} for i, n, s in p]))
            self.players = p
            self.options = None           # controllers are choices in the form
        if self.options is None or c.current is not self.options_of:
            o = self.game_options()
            if o is None:
                return                    # try again next time
            if o != self.options:
                self.send("OPTIONS " + o)
            self.options = o
            self.options_of = c.current

    def game_options(self):
        """The running game's options() as JSON: "[]" if it has none, None if they failed (tried again later)."""
        game = self.controls.current
        if game is None or not hasattr(game, "options"):
            return "[]"
        try:
            fields = game.options()
            return json.dumps([_field(f) for f in fields])
        except MemoryError:
            return None
        except Exception as e:           # a game's bug shouldn't stop the board
            print("options() failed: %r" % e)
            return "[]"

    def shown(self, lights, now):
        """The frame just shown: to the page if it's watching, it changed, and it's time. One allocation a frame
        (the base64), straight to the console when out is given."""
        if not self.watch or now < self.next_frame:
            return
        raw = lights.raw
        if self.last is not None and raw == self.last:
            return
        self.next_frame = now + 1.0 / WATCH_FPS
        try:
            if self.last is None or len(self.last) != len(raw):
                self.last = bytearray(raw)
            else:
                self.last[:] = raw
            b64 = binascii.b2a_base64(self.last)          # ends with a newline
            if self.out is not None:
                self.out(b"@LEDS ")
                self.out(b64)
            else:
                self.send("LEDS " + b64.decode().strip())
        except MemoryError:
            self.last = None                              # send it whole next time


def _field(f):
    """One options() field, with its choices as lists (JSON has no tuples; CircuitPython's json wants lists). What's
    only for the board (a choice's color, player, bar...) stays behind."""
    out = {"key": f["key"], "label": f.get("label", f["key"]),
           "choices": [[str(ch[0]), str(ch[1])] for ch in f["choices"]], "value": str(f.get("value", ""))}
    if f.get("show"):
        out["show"] = {k: [str(x) for x in v] for k, v in f["show"].items()}
    if f.get("note"):
        out["note"] = f["note"]
    return out

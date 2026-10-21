# Desktop test of the USB page's side of the board (gamehost/usbpage.py through the console hub) and of the saved
# settings (gamehost/saved.py): the HELLO answer, state as it changes, players from the page, settings applied and
# remembered, the lights sent (and only when they change, at most WATCH_FPS a second), the page leaving, the
# console's keys and commands still working alongside, and the game chosen at power-up.
#   py -3 tools/test_usbpage.py

import base64
import contextlib
import io
import json
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import config
from gamehost import host, hubs, saved, usbpage
from gamehost.controls import Controls
from gamehost.game import Game as BaseGame
from gamehost.lights import COUNT, Lights

FAILS = []
SIX = 10 ** (-4 / 5)                     # brightness step 6 of 10 (lights.step_brightness): 15.8%


def check(name, ok, detail=""):
    if not ok:
        FAILS.append(name)
        print("FAIL", name, detail)


class FakeSerial:
    """supervisor and sys.stdin as the console hub uses them."""

    def __init__(self):
        self.text = ""
        self.runtime = self
        self.serial_connected = True

    @property
    def serial_bytes_available(self):
        return len(self.text)

    def read(self, n):
        out = self.text[:n]
        self.text = self.text[n:]
        return out


class Recorder(BaseGame):
    def __init__(self, board):
        BaseGame.__init__(self, board)
        self.log = []
        self.color = (0, 0, 0)

    def controller_added(self, c, now):
        self.log.append(("added", c.id))

    def controller_removed(self, c, now):
        self.log.append(("removed", c.id))

    def event(self, c, a, now):
        self.log.append((c.id, a))

    def command(self, text, now):
        return "game: " + text

    def draw(self, lights, now):
        lights.spot("D4", [self.color] * 3)


def with_page():
    """A host running Recorder, with the console (and so the page) on a fake serial port as its only hub."""
    saved.use(bytearray(256))
    h = host.Host(Recorder, host.Board(Lights(), Controls(hardware=False)), name="recorder")
    ser = FakeSerial()
    out = []
    con = hubs.Console(h.board.controls, sup=ser, stdin=ser, write=out.append)
    h.board.controls.hubs.append(con)
    return h, ser, out, con


def taken(out, prefix="@"):
    """The lines sent since the last call that start with prefix (without it)."""
    got = [x[len(prefix):] for x in out if x.startswith(prefix)]
    del out[:]
    return got


def hello():
    h, ser, out, con = with_page()
    h.frame(0.0)
    check("page: nothing before HELLO", out == [], out)
    ser.text = "\n!HELLO page 1\n"
    h.frame(0.025)
    got = taken(out)
    check("page: HELLO answer", got[:2] == ["HELLO 2026.10.20", "BOARD %s %d" % (config.BOARD, COUNT)], got)
    check("page: games", len(got) > 2 and got[2].startswith("GAMES ") and "salient" in got[2].split(), got)
    check("page: config's game and brightness", "STATE default_game " + config.GAME in got and
          "STATE default_brightness %g" % config.BRIGHTNESS in got, got)
    h.frame(0.05)
    got = taken(out)
    check("page: state on the next frame", "STATE game recorder" in got and "STATE brightness default" in got, got)
    pl = [x for x in got if x.startswith("PLAYERS ")]
    check("page: players (none yet)", pl == ["PLAYERS []"], got)
    h.frame(0.075)
    check("page: nothing new, nothing sent", taken(out) == [])
    check("page: no console controllers from page lines", h.board.controls.find("console1") is None)

    ser.text = "!IN p1 up\n!IN p1 pick\n!IN p2 move_back\n!IN p7 up\n!IN p1 jump\n"
    h.frame(0.1)
    check("page: players and presses", h.game.log == [("added", "usb-p1"), ("usb-p1", "up"), ("usb-p1", "pick"),
          ("added", "usb-p2"), ("usb-p2", "move_back")], h.game.log)
    p1 = h.board.controls.find("usb-p1")
    check("page: player name and seat", p1.name == "player 1 (USB)" and p1.seat is None, p1)
    h.frame(0.6)
    pl = [json.loads(x[8:]) for x in taken(out) if x.startswith("PLAYERS ")]
    check("page: players listed", pl and [p["id"] for p in pl[-1]] == ["usb-p1", "usb-p2"], pl)

    # keys and commands typed in a terminal still work (the page sends its console lines with "/")
    ser.text = "p/sound on\r"
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        h.frame(0.65)
    check("page: console keys still work", h.game.log[-1] == ("console1", "pick"), h.game.log[-1:])
    check("page: console commands still work", "game: sound on" in printed.getvalue(), printed.getvalue())

    # a line too long is dropped; the next one still works
    ser.text = "!" + "x" * 400 + "\n!IN p1 down\n"
    h.frame(0.7)
    check("page: long line dropped, next one read", h.game.log[-1] == ("usb-p1", "down"), h.game.log[-1:])

    # the page closes the port: its players leave, nothing more is sent
    ser.serial_connected = False
    h.frame(0.75)
    check("page: players leave with the page", ("removed", "usb-p1") in h.game.log and
          ("removed", "usb-p2") in h.game.log and h.board.controls.find("console1").connected, h.game.log[-3:])
    h.frame(1.5)
    check("page: quiet after it left", taken(out) == [])
    ser.serial_connected = True
    ser.text = "!HELLO page 1\n!IN p1 up\n"
    h.frame(1.6)
    check("page: back again", con.page.active and h.game.log[-2:] == [("added", "usb-p1"), ("usb-p1", "up")],
          h.game.log[-2:])
    ser.text = "!BYE\n"
    h.frame(1.7)
    check("page: BYE", not con.page.active and h.game.log[-1] == ("removed", "usb-p1"), h.game.log[-1:])


def settings():
    h, ser, out, con = with_page()
    ser.text = "!HELLO page 1\n"
    h.frame(0.0)
    h.frame(0.025)
    taken(out)
    ser.text = "!SET brightness 6\n"
    h.frame(0.05)
    got = taken(out)
    check("settings: ACK", "ACK brightness" in got, got)
    h.frame(0.075)
    check("settings: brightness applied", abs(h.board.lights.brightness - SIX) < 1e-9, h.board.lights.brightness)
    check("settings: brightness reported", "STATE brightness 6" in taken(out))
    check("settings: brightness saved", saved.get("brightness") == "6", saved.load())
    ser.text = "!SET brightness 11\n!SET brightness dim\n"
    h.frame(0.1)
    check("settings: bad brightness ignored", saved.get("brightness") == "6" and
          abs(h.board.lights.brightness - SIX) < 1e-9)

    ser.text = "!SET game paint\n"
    h.frame(0.125)
    h.frame(0.15)
    got = taken(out)
    check("settings: game switched and reported", h.name == "paint" and "STATE game paint" in got, got)
    check("settings: game saved", saved.get("game") == "paint", saved.load())
    ser.text = "!SET game nosuchgame\n"
    h.frame(0.175)
    check("settings: no such game: nothing changes", h.name == "paint" and saved.get("game") == "paint")

    # what's saved survives a restart (the same memory read again)
    mem = saved._mem
    saved.use(mem)
    check("settings: read back", saved.load() == {"brightness": "6", "game": "paint"}, saved.load())
    check("settings: starting game is the saved one", host.starting_game()[0] == "paint")
    check("settings: a game named in code wins", host.starting_game("clock")[0] == "clock")
    h2 = host.Host(Recorder, host.Board(Lights(), Controls(hardware=False)), name="recorder")
    h2.restore()
    check("settings: brightness restored", abs(h2.board.lights.brightness - SIX) < 1e-9 and
          h2.board.controls.brightness == "6")
    saved.put("game", "nosuchgame")
    check("settings: a saved game that won't load: config's", host.starting_game()[0] == config.GAME)
    check("settings: and it's forgotten", saved.get("game") is None)

    ser.text = "!SET game default\n!SET brightness default\n"
    h.frame(0.2)
    check("settings: back to config.py", saved.load() == {} and h.name == config.GAME and
          h.board.lights.brightness == config.BRIGHTNESS, (saved.load(), h.name))

    # written only when something changed; junk in the memory is no settings
    writes = []

    class Watched(bytearray):
        def __setitem__(self, k, v):
            writes.append(k)
            bytearray.__setitem__(self, k, v)

    saved.use(Watched(256))
    saved.put("brightness", "4")
    saved.put("brightness", "4")
    saved.put("game", None)
    check("saved: one write for one change", len(writes) == 1, writes)
    saved.forget()
    saved.forget()
    check("saved: forget writes once", len(writes) == 2 and saved.load() == {}, writes)
    saved.use(bytearray(b"\xff" * 256))
    check("saved: blank flash is no settings", saved.load() == {})
    saved.use(bytearray(b"SBS1\xff\xff" + b"\x00" * 250))
    check("saved: a bad length is no settings", saved.load() == {})
    saved.use(bytearray(256))
    saved.put("game", "x" * 300)
    check("saved: too big isn't written", saved.get("game") is None or bytes(saved._mem[:4]) != b"SBS1")


def lights():
    h, ser, out, con = with_page()
    ser.text = "!HELLO page 1\n"
    h.frame(0.0)
    h.frame(0.025)
    taken(out)
    h.frame(0.05)
    check("lights: none until WATCH", not [x for x in taken(out) if x.startswith("LEDS")])
    ser.text = "!WATCH on\n"
    h.game.color = (10, 200, 30)
    h.frame(0.1)
    leds = [x[5:] for x in taken(out) if x.startswith("LEDS ")]
    check("lights: sent after WATCH", len(leds) == 1)
    if leds:
        raw = base64.b64decode(leds[0])
        d4 = 3 * 3 * 18                                   # D4 is spot 18; 3 LEDs, 3 bytes each
        check("lights: all of them, in lights.py's order", len(raw) == COUNT * 3 and
              raw[d4:d4 + 9] == bytes((10, 200, 30) * 3) and sum(raw) == 720, (len(raw), raw[d4:d4 + 9]))
    h.frame(0.2)
    check("lights: unchanged, not sent again", not [x for x in taken(out) if x.startswith("LEDS")])
    h.game.color = (1, 2, 3)
    h.frame(0.225)
    check("lights: changed: sent", len([x for x in taken(out) if x.startswith("LEDS")]) == 1)
    n = 0
    t = 0.25
    while t < 1.25:                                       # changing every frame for a second: about WATCH_FPS
        h.game.color = (int(t * 100) % 255, 0, 0)
        h.frame(t)
        n += len([x for x in taken(out) if x.startswith("LEDS")])
        t += 0.025
    check("lights: at most WATCH_FPS a second", usbpage.WATCH_FPS - 2 <= n <= usbpage.WATCH_FPS + 1, n)
    ser.text = "!WATCH off\n"
    h.game.color = (9, 9, 9)
    h.frame(1.5)
    h.game.color = (8, 8, 8)
    h.frame(1.6)
    check("lights: WATCH off", not [x for x in taken(out) if x.startswith("LEDS")])


class Setter(Recorder):
    """A game with a setup form: one field per controller, and one shown only for "big"."""

    started = None

    def options(self):
        return [{"key": "size", "label": "Size", "choices": (("small", "Small"), ("big", "Big")), "value": "small"},
                {"key": "extra", "label": "Extra", "choices": [(1, "One"), (2, "Two")], "value": 1,
                 "show": {"size": ("big",)}, "note": "only when big"}] + \
               [{"key": c.id, "label": c.name, "choices": [("in", "In")], "value": "in"}
                for c in self.board.controllers]

    def setup(self, choices, now):
        if choices.get("size") == "huge":
            return "Too big."
        Setter.started = dict(choices)
        return None


def options_of(out):
    got = [json.loads(x[8:]) for x in taken(out) if x.startswith("OPTIONS ")]
    return got[-1] if got else None


def setup_form():
    h, ser, out, con = with_page()
    h.game = Setter(h.board)
    h.board.controls.current = h.game
    ser.text = "!HELLO page 1\n"
    h.frame(0.0)
    h.frame(0.025)
    o = options_of(out)
    check("form: options sent", o is not None and [f["key"] for f in o] == ["size", "extra"], o)
    if o:
        check("form: as lists and strings", o[1]["choices"] == [["1", "One"], ["2", "Two"]] and o[1]["value"] == "1"
              and o[1]["show"] == {"size": ["big"]} and o[1]["note"] == "only when big", o[1])
    h.frame(0.05)
    check("form: not again unchanged", options_of(out) is None)
    ser.text = "!IN p1 up\n"
    h.frame(0.1)
    h.frame(0.6)
    o = options_of(out)
    check("form: sent again when a controller arrives", o and o[-1]["key"] == "usb-p1", o)

    ser.text = '!START {"size": "big", "extra": "2", "usb-p1": "in"}\n'
    h.frame(0.65)
    got = taken(out)
    check("form: START reaches setup()", Setter.started == {"size": "big", "extra": "2", "usb-p1": "in"}, Setter.started)
    check("form: SETUP ok", "SETUP ok" in got, got)
    ser.text = '!START {"size": "huge"}\n!START {not json\n'
    h.frame(0.7)
    got = taken(out)
    check("form: setup's message", "SETUP Too big." in got and any(x.startswith("SETUP The setup didn't") for x in got), got)
    ser.text = '!START {"size": "big", "pad": "' + "x" * 900 + '"}\n'
    h.frame(0.75)
    check("form: a long START still arrives", "SETUP ok" in taken(out) and len(Setter.started["pad"]) == 900)

    # a game without a form; NEWGAME makes the game afresh
    h.switch("paint", 0.8)
    h.frame(0.8)
    h.frame(1.4)
    check("form: none for paint", options_of(out) == [])
    before = h.game
    ser.text = "!NEWGAME\n"
    h.frame(1.45)
    check("form: NEWGAME", h.game is not before and h.name == "paint" and h.board.controls.current is h.game and
          "SETUP ok" in taken(out))


def console_help():
    """"help" lists the host's commands, each hub's that has some, and the running game's (their HELP)."""
    from gamehost.radio import Radio

    class Quiet:
        in_waiting = 0

        def write(self, data):
            pass

    h, ser, out, con = with_page()
    h.board.controls.hubs.append(Radio(h.board.controls, Quiet()))
    h.switch("clock", 0.0)
    text = h.command("help")
    check("help: sections", text.startswith("Board:\n") and "\nRadio:\n" in text and "\nclock:\n" in text, text)
    check("help: commands", "  help " in text and "  radio pair " in text and "  time 14:32 " in text, text)
    check("help: a / where the first letter is a key", "  /mem " in text, text)
    check("help: the keys", "Keys: m move" in text and text.endswith("(the USB page adds it)."), text)
    h.switch("paint", 0.1)
    check("help: a game without commands says so", "\npaint:\n  no commands\n" in h.command("help"))
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        ser.text = "help\r"
        h.frame(0.2)
    check("help: typed on the console", "Board:" in printed.getvalue() and "paint:" in printed.getvalue())


def switching():
    """Switching games unloads the old one's modules (so games can take turns in the board's RAM)."""
    saved.use(bytearray(256))
    h = host.Host(host.load_game("paint"), host.Board(Lights(), Controls(hardware=False)), name="paint")
    h.switch("salient", 0.0)
    check("switch: paint unloaded", "games.paint" not in sys.modules and not hasattr(sys.modules["games"], "paint"))
    check("switch: salient loaded", h.name == "salient" and "games.salient.engine" in sys.modules)
    h.switch("clock", 0.1)
    check("switch: salient unloaded, all of it", not [k for k in sys.modules if k.startswith("games.salient")],
          [k for k in sys.modules if k.startswith("games.salient")])
    h.switch("nosuchgame", 0.2)
    check("switch: a failed switch brings the old game back", h.name == "clock" and "games.clock" in sys.modules and
          type(h.game).__module__ == "games.clock")
    h.switch("paint", 0.3)
    h.frame(0.35)
    check("switch: and on to another", h.name == "paint" and "games.clock" not in sys.modules)
    h2 = host.Host(Recorder, host.Board(Lights(), Controls(hardware=False)), name="recorder")
    h2.switch("nosuchgame", 0.0)
    check("switch: a game given in code is kept when a switch fails", isinstance(h2.game, Recorder))

    # A game that doesn't fit in the memory left: saved first, then the program starts afresh with it
    class Restarted(Exception):
        pass

    def no_room(name=None):
        raise MemoryError("memory allocation failed")

    def restart():
        raise Restarted()

    h.restart = restart
    real = host.load_game
    host.load_game = no_room
    try:
        h.apply("game", "salient", 0.4)
        restarted = False
    except Restarted:
        restarted = True
    finally:
        host.load_game = real
    check("switch: no room, so a restart, with the game saved first", restarted and saved.get("game") == "salient",
          saved.get("game"))
    h.restart = None
    msg = h.apply("game", "nosuchgame", 0.5)
    check("switch: no such game: the saved one stays", msg and saved.get("game") == "salient", (msg, saved.get("game")))


def salient_setup():
    """Salient's form and setup(): a side for each controller (or sitting out), the computer on any side no one
    takes (Island Rush is its own game now: tools/test_rush.py)."""
    from games.salient.game import Game as Salient
    ctl = Controls(hardware=False)
    a = ctl.get("usb-p1", "player 1 (USB)", None, ())
    b = ctl.get("wired0", "wired", 4, ())
    g = Salient(host.Board(Lights(), ctl))
    o = {f["key"]: f for f in g.options()}
    check("salient: fields", list(o) == ["side:usb-p1", "side:wired0", "red_seat", "level"], list(o))
    check("salient: a side each, the first Red", [ch[0] for ch in o["side:usb-p1"]["choices"]] == ["out", "red", "blue"]
          and o["side:usb-p1"]["value"] == "red" and o["side:wired0"]["value"] == "out")
    check("salient: the page's form keeps only its parts", usbpage._field(o["side:usb-p1"])["choices"][1] ==
          ["red", "Red, the invader"] and "player" not in usbpage._field(o["side:usb-p1"]))
    base = {"side:usb-p1": "red", "side:wired0": "out", "red_seat": "3", "level": "5"}
    check("salient: invasion starts", g.setup(base, 0.0) is None and g.st is not None)
    check("salient: red at seat 3, blue opposite, the computer blue",
          [(s.seat, s.ctrl) for s in g.seats] == [(3, a), (6, None)] and g.level == 5, [(s.seat, s.ctrl) for s in g.seats])
    check("salient: two humans", g.setup(dict(base, **{"side:wired0": "blue"}), 0.0) is None and g.seats[1].ctrl is b)
    check("salient: computer against computer", g.setup(dict(base, **{"side:usb-p1": "out"}), 0.0) is None and
          g.seats[0].ctrl is None and g.seats[1].ctrl is None)
    check("salient: two on one side", g.setup(dict(base, **{"side:wired0": "red"}), 0.0) ==
          "player 1 (USB) and wired are both Red.")
    o = {f["key"]: f for f in g.options({"side:usb-p1": "out", "side:wired0": "blue"})}
    check("salient: on the board, Red lands opposite a lone Blue", o["red_seat"]["value"] == "1" and "level" in o,
          o["red_seat"]["value"])
    o = {f["key"]: f for f in g.options({"side:usb-p1": "red", "side:wired0": "blue"})}
    check("salient: no difficulty with two players", "level" not in o, list(o))

if __name__ == "__main__":
    hello()
    settings()
    lights()
    setup_form()
    console_help()
    switching()
    salient_setup()
    print("all passed" if not FAILS else "%d failed" % len(FAILS))
    sys.exit(1 if FAILS else 0)

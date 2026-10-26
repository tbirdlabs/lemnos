# Desktop test of the radio hub (gamehost/radio.py) and what the host does with it, over a fake UART: the HELLO
# exchange, controllers coming and going by slot, noise ignored, settings (brightness, switching games), the time
# (walltime.tell, with daylight saving and the RTC chip), the console commands, a session recorded from the radio's
# own C code (radio/test/transcript.txt, written by radio/test/run_tests.py), and a whole two-player Island Rush
# game played with nothing but IN lines from the radio.
#   py -3 tools/test_radio.py

import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import config
import gamehost
from gamehost import host, walltime
from gamehost.controls import Controls
from gamehost.game import Game as BaseGame
from gamehost.lights import Lights
from gamehost.radio import CAN, Radio, parse_time

FAILS = []
SIX = 10 ** (-4 / 5)                     # brightness step 6 of 10 (lights.step_brightness): 15.8%
TRANSCRIPT = os.path.join(HERE, "..", "..", "radio", "test", "transcript.txt")


def check(name, ok, detail=""):
    if not ok:
        FAILS.append(name)
        print("FAIL", name, detail)


class FakeUART:
    """busio.UART as the hub uses it. Bytes fed in arrive at most 32 at a time, so lines arrive in pieces."""

    def __init__(self):
        self.rx = b""
        self.out = b""

    def feed(self, text):
        self.rx += text.encode() if isinstance(text, str) else text

    @property
    def in_waiting(self):
        return min(len(self.rx), 32)

    def read(self, n):
        data, self.rx = self.rx[:n], self.rx[n:]
        return data

    def write(self, data):
        self.out += data

    def sent(self):
        """The lines written since the last call."""
        lines = self.out.decode().split("\n")
        self.out = b""
        return [l for l in lines if l]


class Recorder(BaseGame):
    def __init__(self, board):
        BaseGame.__init__(self, board)
        self.log = []

    def controller_added(self, c, now):
        self.log.append(("added", c.id))

    def controller_removed(self, c, now):
        self.log.append(("removed", c.id))

    def event(self, c, a, now):
        self.log.append((c.id, a))

    def command(self, text, now):
        return "game: " + text


def with_radio(game_class=Recorder, name="recorder"):
    """A host running a game, with a radio on a fake UART as its only hub."""
    h = host.Host(game_class, host.Board(Lights(), Controls(hardware=False)), name=name)
    uart = FakeUART()
    radio = Radio(h.board.controls, uart)
    h.board.controls.hubs.append(radio)
    return h, uart, radio


def run_frames(h, t0, t1, dt=0.025):
    t = t0
    while t < t1:
        h.frame(t)
        t += dt
    return t


def drain(h, uart, t):
    """Frames until everything fed has arrived (32 bytes a frame)."""
    while uart.rx:
        h.frame(t)
        t += 0.025
    h.frame(t)
    return t + 0.025


def link():
    """HELLO until the radio answers; slots become controllers; noise is ignored."""
    h, uart, radio = with_radio()
    h.frame(0.0)
    check("link: HELLO at start", uart.sent() == ["HELLO 2026.10.25"])
    run_frames(h, 0.025, 2.9)
    check("link: not again at once", uart.sent() == [])
    run_frames(h, 3.0, 3.1)
    check("link: again after 3 s", uart.sent() == ["HELLO 2026.10.25"])

    # noise: a floating RX pin, half a line, junk, things out of range
    uart.feed(b"\x00\xff\xfe\x80garbage\n")
    uart.feed("IN p9 up\nIN p0 up\nIN p1 jump\nIN p1\nCTL p7 connected xbox\nCTL p1 sideways\nTIME 2026-13-01T00:00:00\n")
    uart.feed("SET\nWHO knows\n\n" + "x" * 300 + "\n" + "y" * 250)
    drain(h, uart, 3.2)
    check("link: noise makes no controllers or actions", h.game.log == [] and h.board.controllers == [], h.game.log)
    check("link: noise isn't a radio", radio.version is None)
    check("link: a long run with no newline isn't kept", len(radio.buf) <= 200 and radio.skipping, len(radio.buf))
    uart.feed("HELLO dropped: part of the long line\n")
    drain(h, uart, 3.6)
    check("link: the rest of a long line is dropped, up to its newline", radio.version is None)
    check("link: TIME out of range isn't told", walltime._told is None or walltime._told[0][1] != 13)

    uart.out = b""
    uart.feed("HELLO 1.0.0\n")                               # arrives in pieces (32 bytes at a time)
    drain(h, uart, 3.7)
    check("link: radio version", radio.version == "1.0.0")
    sent = uart.sent()
    check("link: answers with its version, the game and the games",
          sent[:2] == ["STATE fw " + gamehost.VERSION, "STATE game recorder"] and sent[2] == "STATE brightness default" and sent[3].startswith("GAMES ") and
          "rush" in sent[3].split(), sent)
    run_frames(h, 3.8, 10.0)
    check("link: no more HELLO once it answered", uart.sent() == [])

    uart.feed("CTL p1 connected xbox\nIN p1 up\nIN p1 pick\nCTL p2 connected wiimote\nIN p2 back\n")
    drain(h, uart, 10.0)
    check("link: two players and their presses", h.game.log == [("added", "radio-p1"), ("radio-p1", "up"),
          ("radio-p1", "pick"), ("added", "radio-p2"), ("radio-p2", "back")], h.game.log)
    p1 = h.board.controls.find("radio-p1")
    check("link: named for its slot and kind", p1.name == "player 1 (Xbox)", p1.name)
    check("link: can arrows, pick and back", p1.can == set(CAN) and p1.seat is None)
    h.game.log = []
    uart.feed("CTL p1 disconnected\n")
    run_frames(h, 10.1, 10.2)
    check("link: disconnected", h.game.log == [("removed", "radio-p1")] and p1 not in h.board.controllers)
    uart.feed("CTL p1 connected phone\nIN p1 left\n")
    drain(h, uart, 10.2)
    check("link: back in its slot: the same controller", h.board.controls.find("radio-p1") is p1 and
          p1 in h.board.controllers and p1.name == "player 1 (phone)" and h.game.log[-1] == ("radio-p1", "left"))

    # the radio restarts: it says HELLO again; we tell it the game again
    uart.feed("HELLO 1.0.1\n")
    drain(h, uart, 10.3)
    check("link: radio restarted", radio.version == "1.0.1" and
          uart.sent()[:2] == ["STATE fw " + gamehost.VERSION, "STATE game recorder"])

    # seats from config.py
    old = config.RADIO_SEATS
    config.RADIO_SEATS = (4, 1)
    try:
        h2, u2, r2 = with_radio()
        u2.feed("CTL p1 connected xbox\nCTL p2 connected xbox\nCTL p3 connected xbox\n")
        drain(h2, u2, 0.0)
        seats = [h2.board.controls.find("radio-p%d" % s).seat for s in (1, 2, 3)]
        check("link: RADIO_SEATS", seats == [4, 1, None], seats)
    finally:
        config.RADIO_SEATS = old


def settings():
    """SET lines: brightness now, another game now (controllers handed over), unknown ones ignored; each ACKed."""
    h, uart, radio = with_radio(host.load_game("paint"), "paint")
    lights = h.board.lights
    start = lights.brightness
    uart.feed("HELLO 1.0.0\nCTL p1 connected xbox\n")
    h.frame(0.0)
    uart.sent()
    uart.feed("SET brightness 6\n")
    h.frame(0.1)
    check("settings: brightness 6 of 10", abs(lights.brightness - SIX) < 1e-9 and abs(config.BRIGHTNESS - SIX) < 1e-9,
          lights.brightness)
    check("settings: ACK", uart.sent() == ["ACK brightness"])
    uart.feed("SET brightness 11\nSET brightness dim\n")
    drain(h, uart, 0.2)
    sent = uart.sent()
    check("settings: the new brightness told to the radio", sent[:1] == ["STATE brightness 6"], sent)
    check("settings: out of range ignored (but ACKed)", abs(lights.brightness - SIX) < 1e-9 and
          sent[1:] == ["ACK brightness", "ACK brightness"], sent)
    uart.feed("SET brightness default\n")
    h.frame(0.3)
    check("settings: default is config.py's again", lights.brightness == start, lights.brightness)
    lights.set_brightness(None)

    paint = h.game
    check("settings: paint has the radio player", any(c.id == "radio-p1" for c in paint.players))
    uart.feed("SET game clock\n")
    h.frame(0.4)
    check("settings: switched to the clock", h.name == "clock" and type(h.game).__module__ == "games.clock.game")
    h.frame(0.5)
    check("settings: tells the radio", "STATE game clock" in uart.sent())
    uart.feed("SET game paint\n")
    h.frame(0.6)
    check("settings: and back: the radio player is handed to the new game",
          h.name == "paint" and h.game is not paint and any(c.id == "radio-p1" for c in h.game.players))
    uart.feed("SET game nosuchgame\nSET colour blue\n")
    h.frame(0.7)
    check("settings: no such game: keeps playing", h.name == "paint")
    names = host.game_names()                         # (every game in games/: sorted, and adding one mustn't break this)
    check("settings: game names", names == sorted(names) and
          {"clock", "paint", "rush", "testpattern", "fire", "fireflies", "aurora", "rain"} <= set(names), names)


class FakeChip:
    def __init__(self):
        self.writes = []

    def read(self):
        return None

    def write(self, t, wday):
        self.writes.append(t)


class FakeNs:
    def __init__(self):
        self.t = 5 * 10 ** 9

    def __call__(self):
        return self.t


def time_of_day():
    """TIME lines: the radio's local time, right on the second; a daylight saving change is written to the chip."""
    h, uart, radio = with_radio()
    uart.feed("TIME 2026-11-01T01:59:58\n")
    h.frame(0.0)
    check("time: TIME is told", walltime._told is not None and walltime._told[0] == (2026, 11, 1, 1, 59, 58))
    check("time: parse", parse_time("2026-10-20T14:05:00") == (2026, 10, 20, 14, 5, 0) and
          parse_time("2026-10-20 14:05") is None and parse_time("2026-02-30T25:00:00") is None)

    ns = FakeNs()
    chip = FakeChip()
    walltime.tell((2026, 11, 1, 1, 59, 58), ns=ns)
    w = walltime.Wall(chip=chip, ns=ns, board_rtc=None)
    check("time: a Wall made after starts from it", w.known and w.hms() == (1, 59, 58), w.hms())
    check("time: written to the chip once", chip.writes == [(2026, 11, 1, 1, 59, 58)], chip.writes)
    ns.t += 1500 * 10 ** 6
    w.update()
    check("time: runs on", w.ms() == (1 * 3600 + 59 * 60 + 59) * 1000 + 500, w.ms())
    ns.t += 500 * 10 ** 6
    walltime.tell((2026, 11, 1, 1, 0, 0), ns=ns)            # fall back: 2:00 CDT is 1:00 CST
    w.update()
    check("time: daylight saving ends: back an hour", w.hms() == (1, 0, 0), w.hms())
    check("time: the change is written to the chip", chip.writes[-1] == (2026, 11, 1, 1, 0, 0) and len(chip.writes) == 2)
    ns.t += 60 * 10 ** 9 + 3 * 10 ** 6
    walltime.tell((2026, 11, 1, 1, 1, 0), ns=ns)            # the next minute, as expected (3 ms late)
    w.update()
    check("time: a minute's tick isn't written", len(chip.writes) == 2, chip.writes)
    check("time: on the second", w.ms() == 3660000, w.ms())
    check("time: describe says where from", "from the radio" in w.describe(), w.describe())
    check("time: the chip isn't read while the radio keeps telling", w.next_read > w.mono())


def commands():
    """'radio' and 'radio pair' go to the radio; anything else to the game."""
    h, uart, radio = with_radio()
    replies = []
    old_print = host.print if hasattr(host, "print") else None
    import builtins
    real = builtins.print
    builtins.print = lambda *a, **k: replies.append(" ".join(str(x) for x in a))
    try:
        h.board.controls.command("radio")
        h.frame(0.0)
        uart.sent()
        h.board.controls.command("radio pair")
        h.board.controls.command("radio pair off")
        h.board.controls.command("time 14:00")
        h.frame(0.1)
    finally:
        builtins.print = real
    check("commands: no radio yet", "none has answered" in replies[0], replies)
    check("commands: pair", uart.sent() == ["PAIR", "PAIR off"])
    check("commands: replies", "pairing mode on" in replies[1] and "off" in replies[2], replies)
    check("commands: others go to the game", replies[3] == "game: time 14:00", replies)


def transcript():
    """A session the radio's own code produced (radio/test/run_tests.py): an Xbox stick held up for half a
    second, a Wiimote's D-pad tapped, A and 1, then the clocks go back and the Wiimote leaves."""
    if not os.path.exists(TRANSCRIPT):
        check("transcript: run radio/test/run_tests.py first", False, TRANSCRIPT)
        return
    h, uart, radio = with_radio()
    uart.feed(open(TRANSCRIPT, "rb").read())
    run_frames(h, 0.0, 1.0)
    want = [("added", "radio-p1"), ("added", "radio-p2"), ("radio-p1", "up"), ("radio-p1", "up"),
            ("radio-p2", "left"), ("radio-p1", "pick"), ("radio-p2", "back"), ("removed", "radio-p2")]
    check("transcript: what the game saw", h.game.log == want, h.game.log)
    check("transcript: brightness", abs(h.board.lights.brightness - SIX) < 1e-9)
    h.board.lights.set_brightness(None)
    check("transcript: the last TIME (after falling back)", walltime._told[0] == (2026, 11, 1, 1, 0, 0), walltime._told)
    check("transcript: radio", radio.version == "1.0.0")


def rush_two_players():
    """A whole two-player Island Rush, both players on radio controllers (an Xbox and a Wiimote), set up on the
    board and played with every press an IN line through the hub and the host; every move must land as picked."""
    import test_rush as TR
    from games.rush import game as G
    h, uart, radio = with_radio(G.Game, "rush")
    g = h.game
    lob = h.lobby
    clk = TR.Clock(h)

    def via_radio(game, clock, c, a):
        uart.feed("IN p%s %s\n" % (c.id[-1], a))
        clock.t += TR.DT
        h.frame(clock.t)

    TR.send = via_radio
    uart.feed("HELLO 1.0.0\nCTL p1 connected xbox\nCTL p2 connected wiimote\n")
    clk.t = drain(h, uart, clk.t)
    c1 = h.board.controls.find("radio-p1")
    c2 = h.board.controls.find("radio-p2")
    check("rush: two radio players", c1 in h.board.controllers and c2 in h.board.controllers)
    for c in (c1, c2):                                       # join, then a corner and a color as offered
        for _ in range(3):
            via_radio(g, clk, c, "pick")
        check("rush: %s joined with a corner and a color" % c.id, lob.choices.get("seat:" + c.id, "out") != "out",
              lob.choices)
    check("rush: p1 leads, on how many play", lob.editing(c1) == "players", lob.editing(c1))
    via_radio(g, clk, c1, "pick")                            # two players
    via_radio(g, clk, c1, "pick")                            # start
    check("rush: started", lob.state == "play", lob.state)
    TR.play_through("rush over the radio", g, clk, {"radio-p1": TR.drive_arrows, "radio-p2": TR.drive_arrows}, 15)
    FAILS.extend(TR.FAILS)
    print("%-40s %s, winner seat %d, round %d, %d moves" % ("two players over the radio", "ok" if not TR.FAILS else "..",
                                                            g.seats[g.st.winner].seat, g.st.round, len(g.st.log)))


if __name__ == "__main__":
    link()
    settings()
    time_of_day()
    commands()
    transcript()
    rush_two_players()
    print("%d failed" % len(FAILS) if FAILS else "all passed")

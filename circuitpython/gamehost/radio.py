# The radio co-processor (radio/ in this repo): an ESP32 that brings Bluetooth controllers (Wiimote, Xbox, Xbox
# Adaptive Controller), phones as controllers, a web settings page and the time of day, over a UART on the
# SCORPIO's TX/RX pins (docs/controllers.md, "The radio"; the protocol is in NOTES.md). A controller hub: each
# player slot p1..p6 on the radio is one controller here, whatever device is in it.
#
# From the radio (text lines, 115200 8N1):
#   HELLO <version>                                   it started, or answered ours
#   IN p1 up|down|left|right|pick|back                a player pressed something
#   CTL p1 connected wiimote|xbox|xac|phone|gamepad   a controller took slot 1;  CTL p1 disconnected
#   TIME 2026-10-20T14:05:00                          local time, sent on the second (walltime.tell)
#   SET brightness 6  /  SET brightness default  /  SET game clock     (the host applies them)
# To the radio:
#   HELLO <version>     at start, again every few seconds until the radio answers
#   STATE game salient  the game running, whenever it changes;  STATE fw 2026.10.20  its version, after a HELLO
#   STATE brightness 6  the brightness setting (1-10 or "default"), after a HELLO and whenever it changes. The board
#                       keeps both settings itself (saved.py), whoever set them; the radio's page follows them
#   GAMES clock paint salient testpattern             the games on the board, after a HELLO
#   ACK <setting>       a SET arrived
#   PAIR / PAIR off     pairing mode (the console's "radio pair" command)
# Unknown lines are ignored both ways. With no radio attached nothing arrives, so nothing changes. The lines are
# read in link.py, which the USB page (usbpage.py) shares.

import config
from . import actions as A
from .link import Link, LONGEST, SLOTS, parse_time, version as _version

CAN = (A.UP, A.DOWN, A.LEFT, A.RIGHT, A.PICK, A.BACK, A.MENU)   # (menu from radio firmware 1.1.0)
KINDS = {"wiimote": "Wiimote", "xbox": "Xbox", "xac": "Xbox Adaptive", "phone": "phone", "gamepad": "gamepad"}
HELLO_EVERY_S = 3.0


class Radio(Link):
    """The radio as a controller hub. uart: anything with in_waiting, read(n) and write(bytes) (tests pass their
    own); by default busio.UART on config.RADIO_TX / RADIO_RX. The lines themselves are link.py's."""

    ID = "radio"
    LABEL = "radio"
    CAN = CAN
    KINDS = KINDS
    HELP = (("radio", "the radio's version and who's connected"),
            ("radio pair", "pairing mode for a minute (radio pair off: stop)"))

    def __init__(self, controls, uart=None):
        Link.__init__(self, controls, getattr(config, "RADIO_SEATS", None))
        if uart is None:
            import board
            import busio
            uart = busio.UART(getattr(board, getattr(config, "RADIO_TX", "TX")),
                              getattr(board, getattr(config, "RADIO_RX", "RX")),
                              baudrate=getattr(config, "RADIO_BAUD", 115200), timeout=0, receiver_buffer_size=1024)
        self.uart = uart
        self.buf = b""
        self.skipping = False           # dropping the rest of a line that was too long
        self.next_hello = 0.0
        self.told_game = None
        self.told_brightness = None

    def send(self, text):
        self.uart.write((text + "\n").encode())

    def games(self):
        from . import host
        return host.game_names()

    def poll(self, now, emit):
        if self.version is None and now >= self.next_hello:
            self.next_hello = now + HELLO_EVERY_S
            self.send("HELLO " + _version())
        if self.version is not None and self.controls.game != self.told_game:
            self.told_game = self.controls.game
            self.send("STATE game " + self.told_game)
        if self.version is not None and self.controls.brightness != self.told_brightness:
            self.told_brightness = self.controls.brightness
            self.send("STATE brightness " + self.told_brightness)
        n = self.uart.in_waiting
        if not n:
            return
        data = self.uart.read(n)
        if not data:
            return
        buf = self.buf + data
        while True:
            k = buf.find(b"\n")
            if k < 0:
                break
            if not self.skipping:
                self.line(buf[:k], now, emit)
            self.skipping = False
            buf = buf[k + 1:]
        if len(buf) > LONGEST:          # noise with no newline: drop it, and the rest of it up to the next newline
            buf = b""
            self.skipping = True
        self.buf = buf

    def hello(self, words):
        first = self.version is None
        self.version = words[1] if len(words) > 1 else "?"
        if first:
            print("Radio %s connected." % self.version)
        self.told_game = self.controls.game
        self.send("STATE fw " + _version())          # (a radio that restarted said HELLO first: it hasn't heard ours)
        self.send("STATE game " + self.told_game)
        self.told_brightness = self.controls.brightness
        self.send("STATE brightness " + self.told_brightness)
        self.send("GAMES " + " ".join(self.games()))

    def command(self, text):
        """Console commands: "radio" (what's connected), "radio pair", "radio pair off". The reply, or None if it
        isn't one. (Not "pair" alone: on the console p is the pick key.)"""
        words = text.lower().split()
        if not words or words[0] != "radio":
            return None
        if len(words) > 1 and words[1] == "pair":
            off = len(words) > 2 and words[2] == "off"
            self.send("PAIR off" if off else "PAIR")
            return "Radio: pairing mode " + ("off." if off else "on for a minute.")
        if self.version is None:
            return "Radio: none has answered (wiring: radio TX to SCORPIO RX, RX to TX, ground)."
        on = [c.name for c in self.controls.connected() if c.id.startswith("radio-")]
        return "Radio %s: %s." % (self.version, ", ".join(on) if on else "no players connected")


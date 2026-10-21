# The text protocol the radio co-processor (radio.py, over a UART) and the USB page (usbpage.py, over the serial
# console) both speak to the board: one line per message, words separated by spaces (NOTES.md, "Radio protocol").
# A Link is a controller hub whose player slots p1..p6 are controllers; a subclass says how lines go out (send) and
# how to answer a HELLO.
#
# Lines in:
#   IN p1 up|down|left|right|pick|back|move|move_back   a player pressed something
#   CTL p1 connected <kind>  /  CTL p1 disconnected      a controller took slot 1, or left it
#   TIME 2026-10-20T14:05:00                            local time, sent right as that second starts
#   SET brightness 6  /  SET game clock  /  ... default  a board setting (the host applies and saves it)
#   HELLO <version>                                     the other side started
# Unknown lines are ignored, so either side can add messages later.

from . import actions as A
from . import walltime

ACTIONS = {"up": A.UP, "down": A.DOWN, "left": A.LEFT, "right": A.RIGHT, "pick": A.PICK, "back": A.BACK,
           "move": A.MOVE, "move_back": A.MOVE_BACK, "menu": A.MENU}
SLOTS = 6
LONGEST = 200                   # a line longer than this is noise


def parse_time(text):
    """"2026-10-20T14:05:00" -> (2026, 10, 20, 14, 5, 0), or None."""
    try:
        d, t = text.split("T")
        y, mo, day = (int(x) for x in d.split("-"))
        h, mi, s = (int(x) for x in t.split(":"))
    except ValueError:
        return None
    if 2000 <= y <= 2099 and 1 <= mo <= 12 and 1 <= day <= 31 and h < 24 and mi < 60 and s < 60:
        return (y, mo, day, h, mi, s)
    return None


class Link:
    """One peer speaking the protocol. ID names its controllers ("radio-p1"), LABEL is for people ("player 1
    (radio)"), CAN is what they can send, KINDS names the kinds in CTL lines."""

    ID = "link"
    LABEL = "link"
    CAN = A.ALL
    KINDS = {}
    MAX_LINE = LONGEST               # longer lines are dropped

    def __init__(self, controls, seats=None):
        self.controls = controls
        self.seats = seats              # the seat each slot sits at, p1 first; None: its player chooses
        self.version = None             # the other side's, once it's said HELLO

    def send(self, text):
        raise NotImplementedError

    def hello(self, words):
        """The other side said HELLO (words[0] == "HELLO")."""

    def controller(self, slot):
        seat = self.seats[slot - 1] if self.seats and slot <= len(self.seats) else None
        return self.controls.get("%s-p%d" % (self.ID, slot), "player %d (%s)" % (slot, self.LABEL), seat, self.CAN)

    def slot(self, word):
        if len(word) >= 2 and word[0] == "p" and word[1:].isdigit():
            n = int(word[1:])
            if 1 <= n <= SLOTS:
                return n
        return 0

    def drop_all(self):
        """Every controller of this link went away (the link itself did)."""
        for n in range(1, SLOTS + 1):
            c = self.controls.find("%s-p%d" % (self.ID, n))
            if c is not None:
                self.controls.remove(c)

    def line(self, raw, now, emit):
        """One line (bytes or str, without its newline). Returns its words if it isn't one of the shared messages
        (so a subclass can take more), else None."""
        if isinstance(raw, bytes):
            if len(raw) > self.MAX_LINE:
                return None
            try:
                raw = raw.decode()
            except UnicodeError:
                return None
        if len(raw) > self.MAX_LINE:
            return None
        words = raw.strip().split()
        if not words:
            return None
        cmd = words[0]
        if cmd == "IN" and len(words) == 3:
            slot = self.slot(words[1])
            a = ACTIONS.get(words[2])
            if slot and a:
                emit(self.controller(slot), a)
        elif cmd == "CTL" and len(words) >= 3:
            slot = self.slot(words[1])
            if not slot:
                return None
            if words[2] == "connected":
                kind = words[3] if len(words) > 3 else "controller"
                c = self.controller(slot)
                c.name = "player %d (%s)" % (slot, self.KINDS.get(kind, kind))
            elif words[2] == "disconnected":
                c = self.controls.find("%s-p%d" % (self.ID, slot))
                if c is not None:
                    self.controls.remove(c)
        elif cmd == "TIME" and len(words) == 2:
            t = parse_time(words[1])
            if t:
                walltime.tell(t)
        elif cmd == "SET" and len(words) >= 3:
            self.controls.setting(words[1], " ".join(words[2:]))
            self.send("ACK " + words[1])
        elif cmd == "HELLO":
            self.hello(words)
        else:
            return words
        return None


def version():
    from . import VERSION
    return VERSION

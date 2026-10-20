# Controller hubs: sources that bring their own controllers, as many as are plugged in or in use, rather than one
# controller per line in config.py. config.CONTROLLER_HUBS lists the ones to start.
#
#   "i2c"       outboard controller boards on the STEMMA QT I2C bus (docs/controllers.md, protocol v1): every
#               (board, pad) is its own controller, such as each Bluetooth gamepad on an ESP32
#   "console"   the USB serial console as up to 6 controllers, for testing: m (move), n (move back), p (pick),
#               b (back), w/a/s/d (up/left/down/right); a digit 1-6 switches which controller the keys belong to.
#               It also takes typed commands for the game (Game.command): a line that starts with any other letter
#               (or with "/") up to Enter, such as "time 14:32" for the clock.
#
# A hub is a class made with the Controls it feeds, with:
#   poll(now, emit)     called every frame; calls emit(controller, action) for each action since the last poll
# It gets its controllers from controls.get(id, name, seat, can) (made the first time, the same object after),
# and calls controls.remove(controller) when one goes away. Your own: "module.Class" in config.py (plugins.py).

import config
from . import actions as A

_bus = None


def i2c_bus():
    """The STEMMA QT I2C bus, made the first time it's asked for and shared after: controller boards, an RTC chip."""
    global _bus
    if _bus is None:
        import board
        import busio
        _bus = busio.I2C(board.SCL, board.SDA, frequency=config.I2C_FREQUENCY)
    return _bus

# I2C protocol v1 (docs/controllers.md): an 8-byte read returns [0x10 | count, event, ...]; each event byte is
# pad << 4 | code.
I2C_CODES = {1: A.MOVE, 2: A.MOVE_BACK, 3: A.PICK, 4: A.BACK, 5: A.UP, 6: A.DOWN, 7: A.LEFT, 8: A.RIGHT}
I2C_ONE_SWITCH = 9        # the pad has only a switch (the board scans for it): no back
I2C_GONE = 15             # the pad disconnected


class I2CBoards:
    def __init__(self, controls):
        self.controls = controls
        self.i2c = i2c_bus()
        self.nodes = []
        self.buf = bytearray(8)
        self.next_scan = 0.0

    def scan(self):
        if not self.i2c.try_lock():
            return
        try:
            found = self.i2c.scan()
        finally:
            self.i2c.unlock()
        self.nodes = [a for a in found if a in config.I2C_ADDRESSES]

    def poll(self, now, emit):
        if now >= self.next_scan:
            self.next_scan = now + config.I2C_RESCAN_S
            self.scan()
        if not self.nodes or not self.i2c.try_lock():
            return
        try:
            for addr in self.nodes:
                try:
                    self.i2c.readfrom_into(addr, self.buf)
                except OSError:
                    continue
                if self.buf[0] >> 4 != 1:
                    continue
                for k in range(1, 1 + min(7, self.buf[0] & 0x0F)):
                    b = self.buf[k]
                    pad, code = b >> 4, b & 0x0F
                    cid = "i2c-%02x-%d" % (addr, pad)
                    if code == I2C_GONE:
                        c = self.controls.find(cid)
                        if c is not None:
                            self.controls.remove(c)
                        continue
                    c = self.controls.get(cid, "pad %d on 0x%02x" % (pad, addr), None, A.ALL)
                    if code == I2C_ONE_SWITCH:
                        c.can = set(A.ONE_SWITCH)
                    elif code in I2C_CODES:
                        emit(c, I2C_CODES[code])
        finally:
            self.i2c.unlock()


CONSOLE_KEYS = {"m": A.MOVE, "n": A.MOVE_BACK, "p": A.PICK, "b": A.BACK,
                "w": A.UP, "s": A.DOWN, "a": A.LEFT, "d": A.RIGHT}


class Console:
    """The USB serial console as up to 6 controllers (for testing), and a command line for the game."""

    def __init__(self, controls):
        import supervisor
        import sys
        self.sup = supervisor
        self.stdin = sys.stdin
        self.controls = controls
        self.which = 1
        self.line = None           # a command being typed, or None

    def typed(self, ch):
        """One character of a command line: echoed, since the console doesn't echo while code runs."""
        if ch in "\r\n":
            print()
            if self.line.strip():
                self.controls.command(self.line.strip())
            self.line = None
        elif ch in "\b\x7f":
            if self.line:
                self.line = self.line[:-1]
                print("\b \b", end="")
        elif ch >= " ":
            self.line += ch
            print(ch, end="")

    def poll(self, now, emit):
        n = self.sup.runtime.serial_bytes_available
        if not n:
            return
        for ch in self.stdin.read(n):
            if self.line is not None:
                self.typed(ch)
            elif ch == "/" or (ch.isalpha() and ch.lower() not in CONSOLE_KEYS):
                self.line = ""
                if ch != "/":
                    self.typed(ch)
            elif "1" <= ch <= "6":
                self.which = int(ch)
            elif ch.lower() in CONSOLE_KEYS:
                c = self.controls.get("console%d" % self.which, "console %d" % self.which, None, A.ALL)
                emit(c, CONSOLE_KEYS[ch.lower()])


HUBS = {"i2c": I2CBoards, "console": Console}

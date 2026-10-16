# Controllers: turns the wired inputs (config.CONTROLLERS), outboard I2C controller boards and the serial console
# into (controller, action) pairs. Games never see pins or devices, only Controller objects and actions:
#   move, move_back, pick, back, up, down, left, right
# A Controller has .id, .name, .seat (1-6 or None) and .can (the set of actions it can produce), so a game can
# tell, for example, that a one-switch controller has no back and offer a "way out" stop instead.
# To add a new kind of input, write a class with can (a set) and poll(now, emit), and add it to SOURCES.

import time
import config

ACTIONS = ("move", "move_back", "pick", "back", "up", "down", "left", "right")
ALL = ACTIONS
DEBOUNCE_S = 0.02

try:
    import board
    import digitalio
    HARDWARE = True
except ImportError:          # desktop Python: only feed() produces actions
    HARDWARE = False


class Controller:
    def __init__(self, cid, name, seat, can):
        self.id = cid
        self.name = name
        self.seat = seat
        self.can = set(can)

    def __repr__(self):
        return "<%s seat %s>" % (self.name, self.seat)


def _pin(name):
    return getattr(board, name)


def _switch(name):
    io = digitalio.DigitalInOut(_pin(name))
    io.switch_to_input(pull=digitalio.Pull.UP)
    return io


class Button:
    """One switch to ground. Press = `does`; with `hold`, a press held hold_s or longer gives `hold` instead."""

    def __init__(self, spec):
        self.io = _switch(spec["pin"])
        self.does = spec.get("does", "pick")
        self.hold = spec.get("hold")
        self.hold_s = spec.get("hold_s", 0.8)
        self.can = {self.does} | ({self.hold} if self.hold else set())
        self.down = False
        self.changed = 0.0
        self.fired = False

    def poll(self, now, emit):
        pressed = not self.io.value
        if pressed != self.down and now - self.changed >= DEBOUNCE_S:
            self.down = pressed
            self.changed = now
            if pressed:
                self.fired = False
                if not self.hold:
                    emit(self.does)
            elif self.hold and not self.fired:
                emit(self.does)
        elif self.down and self.hold and not self.fired and now - self.changed >= self.hold_s:
            self.fired = True
            emit(self.hold)


class Encoder:
    """A rotary encoder: each detent clockwise = move, counterclockwise = move_back."""

    def __init__(self, spec):
        import rotaryio
        self.enc = rotaryio.IncrementalEncoder(_pin(spec["a"]), _pin(spec["b"]), divisor=spec.get("divisor", 4))
        self.last = self.enc.position
        self.sign = -1 if spec.get("reverse") else 1
        self.can = {"move", "move_back"}

    def poll(self, now, emit):
        pos = self.enc.position
        d = (pos - self.last) * self.sign
        self.last = pos
        for _ in range(min(abs(d), 4)):
            emit("move" if d > 0 else "move_back")


class Scan(Button):
    """One switch with auto-scan: the board steps (move) every `every` seconds; the switch picks."""

    def __init__(self, spec):
        spec = dict(spec)
        spec["does"] = "pick"
        Button.__init__(self, spec)
        self.every = spec.get("every", 1.5)
        self.next = 0.0
        self.can = self.can | {"move"}

    def poll(self, now, emit):
        def emit2(a):
            self.next = now + self.every          # a pick (or back) restarts the wait
            emit(a)
        Button.poll(self, now, emit2)
        if self.down:
            self.next = now + self.every
        elif now >= self.next:
            self.next = now + self.every
            emit("move")


class Ladder:
    """Several switches on one analog pin through resistors. bands: ((low V, high V, action), ...)."""

    def __init__(self, spec):
        import analogio
        self.adc = analogio.AnalogIn(_pin(spec["pin"]))
        self.bands = spec["bands"]
        self.can = set(b[2] for b in self.bands)
        self.seen = None
        self.held = None
        self.since = 0.0

    def poll(self, now, emit):
        v = self.adc.value * 3.3 / 65535
        hit = None
        for lo, hi, a in self.bands:
            if lo <= v <= hi:
                hit = a
                break
        if hit != self.seen:
            self.seen = hit
            self.since = now
        elif hit != self.held and now - self.since >= DEBOUNCE_S:
            self.held = hit
            if hit:
                emit(hit)


SOURCES = {"button": Button, "encoder": Encoder, "scan": Scan, "ladder": Ladder}

# I2C protocol v1 (docs/controllers.md): an 8-byte read returns [0x10 | count, event, ...]; each event byte is
# pad << 4 | code.
I2C_CODES = {1: "move", 2: "move_back", 3: "pick", 4: "back", 5: "up", 6: "down", 7: "left", 8: "right"}
I2C_ONE_SWITCH = 9        # the pad has only a switch (the board scans for it): no back
I2C_GONE = 15             # the pad disconnected


class I2CBoards:
    def __init__(self, controls):
        import busio
        self.controls = controls
        self.i2c = busio.I2C(board.SCL, board.SDA, frequency=config.I2C_FREQUENCY)
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

    def poll(self, now, emit_for):
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
                    c = self.controls.get(cid, "pad %d on 0x%02x" % (pad, addr), None, ALL)
                    if code == I2C_ONE_SWITCH:
                        c.can = {"move", "pick"}
                    elif code in I2C_CODES:
                        emit_for(c, I2C_CODES[code])
        finally:
            self.i2c.unlock()


SERIAL_KEYS = {"m": "move", "n": "move_back", "p": "pick", "b": "back", "w": "up", "s": "down", "a": "left", "d": "right"}


class Console:
    """The USB serial console as up to 6 controllers (for testing)."""

    def __init__(self, controls):
        import supervisor
        import sys
        self.sup = supervisor
        self.stdin = sys.stdin
        self.controls = controls
        self.which = 1

    def poll(self, now, emit_for):
        n = self.sup.runtime.serial_bytes_available
        if not n:
            return
        for ch in self.stdin.read(n):
            if "1" <= ch <= "6":
                self.which = int(ch)
            elif ch.lower() in SERIAL_KEYS:
                c = self.controls.get("console%d" % self.which, "console %d" % self.which, None, ALL)
                emit_for(c, SERIAL_KEYS[ch.lower()])


class Controls:
    def __init__(self, hardware=HARDWARE):
        self.controllers = []
        self.sources = []          # (source, controller)
        self.boards = []           # sources that make their own controllers (I2C, console)
        self.queue = []
        if not hardware:
            return
        for k, spec in enumerate(config.CONTROLLERS):
            c = self.get("wired%d" % k, spec.get("name", "wired %d" % (k + 1)), spec.get("seat"), ())
            for inp in spec["inputs"]:
                try:
                    src = SOURCES[inp["type"]](inp)
                except Exception as e:          # a missing pin or library shouldn't stop the board
                    print("controller %s: %s input not set up: %s" % (c.name, inp.get("type"), e))
                    continue
                c.can |= src.can
                self.sources.append((src, c))
        if config.I2C_CONTROLLERS:
            try:
                self.boards.append(I2CBoards(self))
            except Exception as e:
                print("I2C controllers not set up:", e)
        if config.SERIAL_CONTROLLER:
            try:
                self.boards.append(Console(self))
            except Exception as e:
                print("serial console controller not set up:", e)

    def get(self, cid, name, seat, can):
        """The controller with this id, made on first use."""
        for c in self.controllers:
            if c.id == cid:
                return c
        c = Controller(cid, name, seat, can)
        self.controllers.append(c)
        return c

    def feed(self, controller, action):
        """Queue an action as if the controller had sent it (desktop tests, other code)."""
        self.queue.append((controller, action))

    def poll(self, now=None):
        """Every (controller, action) since the last call, oldest first."""
        if now is None:
            now = time.monotonic()
        out = self.queue
        self.queue = []
        for src, c in self.sources:
            src.poll(now, lambda a, c=c: out.append((c, a)))
        for b in self.boards:
            b.poll(now, lambda c, a: out.append((c, a)))
        return out

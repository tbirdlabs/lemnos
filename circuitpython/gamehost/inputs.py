# Wired input devices: switches, encoders and switch boxes on the board's own pins, each turned into actions
# (actions.py). config.CONTROLLERS lists them under the controller (player) they belong to; see docs/controllers.md.
#
# An input is a class made from its line in config.py (a dict, `spec`), with:
#   can                 the set of actions it can send
#   poll(now, emit)     called every frame; calls emit(action) once for each action since the last poll
# To add your own, write one (in its own file is fine) and name it in config.py as "module.Class" (plugins.py),
# or add it to INPUTS below.

from . import actions as A

DEBOUNCE_S = 0.02


def _pin(name):
    import board
    return getattr(board, name)


def _switch(name):
    import digitalio
    io = digitalio.DigitalInOut(_pin(name))
    io.switch_to_input(pull=digitalio.Pull.UP)
    return io


class Button:
    """One switch to ground. Press = `does`; with `hold`, a press held hold_s or longer gives `hold` instead.
    spec: pin, does (default pick), hold, hold_s (default 0.8)."""

    def __init__(self, spec):
        self.io = _switch(spec["pin"])
        self.does = spec.get("does", A.PICK)
        self.hold = spec.get("hold")
        self.hold_s = spec.get("hold_s", 0.8)
        self.can = {self.does} | ({self.hold} if self.hold else set())
        self.down = False
        self.changed = 0.0
        self.fired = False

    def pressed(self):
        return not self.io.value                 # pulled up; the switch shorts it to ground

    def poll(self, now, emit):
        pressed = self.pressed()
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
    """A rotary encoder: each detent clockwise = move, counterclockwise = move_back.
    spec: a, b (two consecutive GPIOs), reverse, divisor (default 4)."""

    def __init__(self, spec):
        import rotaryio
        self.enc = rotaryio.IncrementalEncoder(_pin(spec["a"]), _pin(spec["b"]), divisor=spec.get("divisor", 4))
        self.last = self.enc.position
        self.sign = -1 if spec.get("reverse") else 1
        self.can = {A.MOVE, A.MOVE_BACK}

    def poll(self, now, emit):
        pos = self.enc.position
        d = (pos - self.last) * self.sign
        self.last = pos
        for _ in range(min(abs(d), 4)):
            emit(A.MOVE if d > 0 else A.MOVE_BACK)


class Scan(Button):
    """One switch with auto-scan: the board steps (move) every `every` seconds; the switch picks.
    spec: pin, every (default 1.5), hold (say "back", for a long press)."""

    def __init__(self, spec):
        spec = dict(spec)
        spec["does"] = A.PICK
        Button.__init__(self, spec)
        self.every = spec.get("every", 1.5)
        self.next = 0.0
        self.can = self.can | {A.MOVE}

    def poll(self, now, emit):
        def emit2(a):
            self.next = now + self.every          # a pick (or back) restarts the wait
            emit(a)
        Button.poll(self, now, emit2)
        if self.down:
            self.next = now + self.every
        elif now >= self.next:
            self.next = now + self.every
            emit(A.MOVE)


class Ladder:
    """Several switches on one analog pin through resistors. spec: pin, bands ((low V, high V, action), ...);
    nothing pressed = no band."""

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


INPUTS = {"button": Button, "encoder": Encoder, "scan": Scan, "ladder": Ladder}

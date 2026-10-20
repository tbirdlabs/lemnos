# The time of day, for any game (the clock, a night dimmer): from a real-time clock chip on the STEMMA QT I2C bus if
# config.RTC names one, else from the board's own clock, which forgets the time at power-off. Setting the time sets
# both, so with a chip (on its coin cell) it only needs setting once.
#
#   from gamehost import walltime
#   w = walltime.Wall()          # once: finds the chip and reads it
#   w.update()                   # every frame: keeps in step with the chip
#   w.ms()                       # milliseconds since midnight
#   w.known                      # False until the time has been set (no chip and no setting, or the chip lost it)
#   w.set(14, 32, 0)             # with a date too: w.set(14, 32, 0, (2026, 10, 20))
#   w.command("time 14:32")      # a console command (Game.command): the reply to print, or None if it isn't one
#
# Kept in whole milliseconds from time.monotonic_ns(), so it stays exact however long the board runs
# (time.monotonic() is a float that loses precision after a day or so). The board's own clock and a chip both
# count whole seconds, so on reading one the board waits for its seconds to tick over (up to a second, a frame at
# a time) and starts the milliseconds there. A chip is read again every 15 minutes; it's the better clock.
# Local time only, no time zones: change it for daylight saving time.

import time
import config

DAY = 86400000
SYNC_MS = 15 * 60 * 1000                 # how often to read the chip again
RETRY_MS = 60 * 1000                     # after a read that failed
NO_DATE = (2001, 1, 1)                   # the date set with a time alone when the board has none


def _bcd(b):
    return (b >> 4) * 10 + (b & 15)


def _to_bcd(n):
    return (n // 10) << 4 | n % 10


def weekday(y, m, d):
    """0 = Monday ... 6 = Sunday (time.struct_time's tm_wday)."""
    t = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    if m < 3:
        y -= 1
    return (y + y // 4 - y // 100 + y // 400 + t[m - 1] + d + 6) % 7


def _valid(y, mo, d, h, mi, s):
    if 1 <= mo <= 12 and 1 <= d <= 31 and h < 24 and mi < 60 and s < 60:
        return (y, mo, d, h, mi, s)
    return None


class Chip:
    """An RTC chip at ADDR. read(): (year, month, day, hour, minute, second), or None if it can't be read or has
    lost the time (its battery ran out). write((year, month, day, hour, minute, second), weekday): set and start it."""
    ADDR = 0x68

    def __init__(self, i2c):
        self.i2c = i2c
        self.buf = bytearray(8)

    def present(self):
        while not self.i2c.try_lock():
            pass
        try:
            return self.ADDR in self.i2c.scan()
        finally:
            self.i2c.unlock()

    def _read(self, reg, n):
        if not self.i2c.try_lock():
            return None
        try:
            self.i2c.writeto_then_readfrom(self.ADDR, bytes((reg,)), self.buf, in_end=n)
            return bytes(self.buf[:n])
        except OSError:
            return None
        finally:
            self.i2c.unlock()

    def _write(self, reg, data):
        while not self.i2c.try_lock():
            pass
        try:
            self.i2c.writeto(self.ADDR, bytes((reg,)) + bytes(data))
        finally:
            self.i2c.unlock()


class DS1307(Chip):
    """Time in registers 0-6; bit 7 of the seconds stops the clock."""

    def read(self):
        b = self._read(0, 7)
        if b is None or b[0] & 0x80:
            return None
        h = b[2]
        if h & 0x40:                     # 12-hour mode (this module writes 24)
            h = _bcd(h & 0x1F) % 12 + (12 if h & 0x20 else 0)
        else:
            h = _bcd(h & 0x3F)
        return _valid(2000 + _bcd(b[6]), _bcd(b[5] & 0x1F), _bcd(b[4] & 0x3F), h, _bcd(b[1] & 0x7F), _bcd(b[0] & 0x7F))

    def write(self, t, wday):
        y, mo, d, h, mi, s = t
        self._write(0, (_to_bcd(s), _to_bcd(mi), _to_bcd(h), wday + 1, _to_bcd(d), _to_bcd(mo), _to_bcd(y % 100)))


class DS3231(DS1307):
    """The DS1307's time registers; the oscillator-stopped flag (bit 7 of register 0x0F) says it lost the time."""

    def read(self):
        b = self._read(0x0F, 1)
        if b is None or b[0] & 0x80:
            return None
        return DS1307.read(self)

    def write(self, t, wday):
        DS1307.write(self, t, wday)
        b = self._read(0x0F, 1)
        if b is not None:
            self._write(0x0F, (b[0] & 0x7F,))


class PCF8523(Chip):
    """Time in registers 3-9; bit 7 of the seconds says it lost the time. Writing also turns on the switch to the
    battery at power-off (off from the factory) and makes sure it's running in 24-hour mode."""

    def read(self):
        b = self._read(3, 7)
        if b is None or b[0] & 0x80:
            return None
        return _valid(2000 + _bcd(b[6]), _bcd(b[5] & 0x1F), _bcd(b[3] & 0x3F), _bcd(b[2] & 0x3F), _bcd(b[1] & 0x7F),
                      _bcd(b[0] & 0x7F))

    def write(self, t, wday):
        y, mo, d, h, mi, s = t
        c = self._read(0, 3)
        if c is not None:
            self._write(0, (c[0] & ~0x28 & 0xFF,))      # running (STOP off), 24-hour
            self._write(2, (c[2] & 0x1F,))              # battery switch-over: standard mode
        self._write(3, (_to_bcd(s), _to_bcd(mi), _to_bcd(h), _to_bcd(d), wday, _to_bcd(mo), _to_bcd(y % 100)))


CHIPS = {"ds3231": DS3231, "ds1307": DS1307, "pcf8523": PCF8523}


def find_chip(name=None):
    """The chip config.RTC names, if it answers on the I2C bus; else None."""
    name = name if name is not None else getattr(config, "RTC", None)
    if not name:
        return None
    if name not in CHIPS:
        print("config.RTC must be one of %s, or None" % (tuple(CHIPS),))
        return None
    try:
        from .hubs import i2c_bus
        chip = CHIPS[name](i2c_bus())
        if chip.present():
            return chip
        print("No %s RTC chip on the I2C bus: keeping time on the board only." % name)
    except Exception as e:               # no I2C pull-ups (nothing plugged in), no busio on the desktop
        print("No RTC chip (%s): keeping time on the board only." % e)
    return None


def _board_rtc():
    try:
        import rtc
        return rtc.RTC()
    except ImportError:                  # the desktop
        return None


class Wall:
    """The time of day. chip: an RTC chip object, None for none, or "config" to find the one config.RTC names.
    ns: the nanosecond counter (time.monotonic_ns; tests pass their own). board_rtc: the board's clock (rtc.RTC())
    or None; "auto" finds it on CircuitPython."""

    def __init__(self, chip="config", ns=None, board_rtc="auto"):
        self.ns = ns or time.monotonic_ns
        self.chip = find_chip() if chip == "config" else chip
        self.rtc = _board_rtc() if board_rtc == "auto" else board_rtc
        self.base = 0                    # the time of day (ms) at mono() == at
        self.at = self.mono()
        self.known = False
        self.wait = None                 # reading a clock until its seconds tick over: [which, first seconds, give up]
        self.next_read = 0
        self.chip_ok = None              # the last chip read: True, False (failed or lost the time), None (none yet)
        if self.chip is not None:
            self.next_read = self.at
        elif self.board_time() is not None:
            self._begin("board", self.at)            # set before a reload: it's still running

    def mono(self):
        return self.ns() // 1000000

    def ms(self):
        """Milliseconds since midnight."""
        return (self.base + self.mono() - self.at) % DAY

    def hms(self):
        s = self.ms() // 1000
        return s // 3600, s // 60 % 60, s % 60

    def board_time(self):
        """The board's own clock as (year, month, day, hour, minute, second), if it's been set since power-up."""
        if self.rtc is None:
            return None
        t = time.localtime()
        return tuple(t[:6]) if t[0] >= NO_DATE[0] else None

    def date(self):
        t = self.board_time()
        return t[:3] if t else NO_DATE

    def _start(self, h, mi, s, m):
        self.base = (h * 3600 + mi * 60 + s) * 1000
        self.at = m
        self.known = True

    def _begin(self, which, m):
        self.wait = [which, None, m + 2500]

    def update(self):
        """Call every frame: reads the chip every 15 minutes (or the board's clock after a reload, with no chip)."""
        m = self.mono()
        if self.wait is None:
            if self.chip is None or m < self.next_read:
                return
            self._begin("chip", m)
        which, first, give_up = self.wait
        t = self.chip.read() if which == "chip" else self.board_time()
        if t is None or m > give_up:     # can't be read, lost the time, or its seconds never moved
            self.wait = None
            if which == "chip":
                self.chip_ok = False
                self.next_read = m + RETRY_MS
                if not self.known and self.board_time() is not None:
                    self._begin("board", m)
            return
        if first is None:
            self.wait[1] = t[5]
            if not self.known:           # show it now, to the second; the tick makes it exact
                self._start(t[3], t[4], t[5], m)
            return
        if t[5] == first:
            return
        self._start(t[3], t[4], t[5], m)
        self.wait = None
        if which == "chip":
            self.chip_ok = True
            self._set_board(t)
            self.next_read = m + SYNC_MS

    def _set_board(self, t):
        if self.rtc is not None:
            self.rtc.datetime = time.struct_time(t + (weekday(*t[:3]), -1, -1))

    def set(self, h, mi, s=0, date=None):
        """Set the time (24-hour), and the date if given (else it keeps the board's, or 2001-01-01): on the board,
        and on the chip if there is one."""
        t = tuple(date or self.date()) + (h, mi, s)
        self._start(h, mi, s, self.mono())
        self.wait = None
        self._set_board(t)
        if self.chip is not None:
            try:
                self.chip.write(t, weekday(*t[:3]))
                self.chip_ok = True
            except OSError:
                self.chip_ok = False
            self.next_read = self.mono() + SYNC_MS

    def describe(self):
        h, mi, s = self.hms()
        y, mo, d = self.date()
        out = "%02d:%02d:%02d" % (h, mi, s)
        if self.board_time() is not None:
            out = "%04d-%02d-%02d " % (y, mo, d) + out
        if not self.known:
            out += " (not set)"
        if self.chip is not None:
            out += ", RTC chip " + {True: "ok", False: "not read or lost the time", None: "not read yet"}[self.chip_ok]
        return out

    def command(self, text):
        """"time" says the time; "time 14:32", "time 2:32pm", "time 14:32:05", "time 2026-10-20 14:32:05" set it.
        Returns the reply, or None if text isn't a time command."""
        words = text.lower().replace("p.m.", "pm").replace("a.m.", "am").split()
        if not words or words[0] not in ("time", "t", "settime"):
            return None
        words = words[1:]
        if not words:
            return "The time is " + self.describe() + "."
        date = None
        hms = None
        half = None
        try:
            for w in words:
                if w.endswith("am") or w.endswith("pm"):
                    half = w[-2:]
                    w = w[:-2]
                    if not w:
                        continue
                if "-" in w:
                    y, mo, d = (int(x) for x in w.split("-"))
                    if y < 100:
                        y += 2000
                    if not (2000 <= y <= 2099 and 1 <= mo <= 12 and 1 <= d <= 31):
                        raise ValueError
                    date = (y, mo, d)
                elif ":" in w:
                    p = [int(x) for x in w.split(":")]
                    if len(p) < 2 or len(p) > 3:
                        raise ValueError
                    hms = (p + [0])[:3]
                else:
                    raise ValueError
            if hms is None:
                raise ValueError
            h, mi, s = hms
            if half:
                if not 1 <= h <= 12:
                    raise ValueError
                h = h % 12 + (12 if half == "pm" else 0)
            if not (0 <= h < 24 and 0 <= mi < 60 and 0 <= s < 60):
                raise ValueError
        except ValueError:
            return "Type the time like: time 14:32, time 2:32pm, time 14:32:05, or time 2026-10-20 14:32:05"
        self.set(h, mi, s, date)
        return "Set: " + self.describe() + "."

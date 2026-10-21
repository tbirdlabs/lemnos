# Settings the board remembers through power-off: what was last set from the USB page (Salient.html) or the radio's
# web page, "game" (the one to start at power-up) and "brightness" (1-10). config.py keeps the defaults; a saved
# setting wins over it until it's set back to "default" (or forget() runs: the page's "Back to config.py").
# They live in the RP2040's non-volatile memory (microcontroller.nvm), which CircuitPython can write even while the
# CIRCUITPY drive is open on a computer. Desktop Python keeps them in memory only.
#
#   saved.get("game")             "clock", or None if nothing is saved
#   saved.put("brightness", "6")  remembered (written only if it changed); put(key, None) forgets it

MAGIC = b"SBS1"                 # then 2 bytes of length, then "key=value\n" lines
ROOM = 256

_mem = None
_cache = None


def _memory():
    global _mem
    if _mem is None:
        try:
            import microcontroller
            _mem = microcontroller.nvm
        except (ImportError, AttributeError):
            _mem = None
        if _mem is None:
            _mem = bytearray(ROOM)
    return _mem


def use(memory):
    """Keep the settings in `memory` (a bytearray) from now on (tests)."""
    global _mem, _cache
    _mem = memory
    _cache = None


def load():
    """Every saved setting: {key: value}."""
    global _cache
    if _cache is None:
        _cache = {}
        m = _memory()
        if bytes(m[0:4]) == MAGIC:
            n = m[4] | m[5] << 8
            if n <= ROOM - 6:
                try:
                    text = bytes(m[6:6 + n]).decode()
                except UnicodeError:
                    text = ""
                for ln in text.split("\n"):
                    if "=" in ln:
                        k, v = ln.split("=", 1)
                        _cache[k] = v
    return _cache


def get(key, default=None):
    return load().get(key, default)


def _write(d):
    body = "".join("%s=%s\n" % (k, d[k]) for k in sorted(d)).encode()
    if len(body) > ROOM - 6:
        return False
    data = MAGIC + bytes((len(body) & 255, len(body) >> 8)) + body
    m = _memory()
    try:
        m[0:len(data)] = data
    except OSError as e:            # the flash couldn't be written: keep running on what's in memory
        print("Settings not saved (%s)." % e)
        return False
    return True


def put(key, value):
    """Remember key = value (a string), or forget it (None). Writes only if it changed."""
    d = load()
    if value is None:
        if key not in d:
            return
        del d[key]
    else:
        value = str(value)
        if "\n" in value or "=" in key or d.get(key) == value:
            return
        d[key] = value
    _write(d)


def forget():
    """Forget every saved setting (config.py's again from the next start)."""
    d = load()
    if d:
        d.clear()
        _write(d)

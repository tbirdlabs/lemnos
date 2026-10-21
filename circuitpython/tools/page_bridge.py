# A desktop stand-in for the board on stdin/stdout, for tools/test_page.js: the real host and console hub (so the
# real USB page protocol, usbpage.py), with the bits of CircuitPython around them that the page relies on: Ctrl-C
# stops the program ("Press any key to enter the REPL"), a key then gives a REPL prompt that understands only
# "s.forget()", and Ctrl-D restarts ("soft reboot", "code.py output:"), keeping the saved settings in memory.
#   py -3 tools/page_bridge.py

import os
import sys
import threading
import time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from gamehost import host, hubs, saved
from gamehost.controls import Controls
from gamehost.lights import Lights

out = sys.stdout.buffer        # bytes, so Windows doesn't turn "\r\n" into "\r\r\n"
lock = threading.Lock()


def say(text, end="\r\n"):
    with lock:
        out.write((text + end).encode())
        out.flush()


class Serial:
    """supervisor.runtime and sys.stdin as the console hub uses them, fed by a thread reading the real stdin."""

    def __init__(self):
        self.text = ""
        self.runtime = self
        self.serial_connected = True

    @property
    def serial_bytes_available(self):
        return len(self.text)

    def read(self, n):
        with lock:
            got, self.text = self.text[:n], self.text[n:]
        return got


ser = Serial()
keys = []                       # control characters, for the main loop


def reader():
    raw = sys.stdin.buffer
    while True:
        b = raw.read(1)
        if not b:
            ser.serial_connected = False
            keys.append("eof")
            return
        ch = b.decode("latin-1")
        if ch in "\x03\x04" or mode[0] != "running":
            keys.append(ch)
        else:
            with lock:
                ser.text += ch


mode = ["running"]
saved.use(bytearray(256))


def start():
    say("code.py output:")
    name, cls = host.starting_game()
    h = host.Host(cls, host.Board(Lights(), Controls(hardware=False)), name=name)
    h.restore()
    con = hubs.Console(h.board.controls, sup=ser, stdin=ser, write=lambda s: say(s))
    h.board.controls.hubs.append(con)
    return h


def main():
    import builtins
    builtins.print = lambda *a, **k: say(" ".join(str(x) for x in a), k.get("end", "\r\n"))
    threading.Thread(target=reader, daemon=True).start()
    h = start()
    line = ""
    while True:
        while keys:
            k = keys.pop(0)
            if k == "eof":
                return
            if k == "\x04":
                say("soft reboot")
                ser.text = ""
                mode[0] = "running"
                h = start()
            elif mode[0] == "running" and k == "\x03":
                say("Traceback (most recent call last):\r\nKeyboardInterrupt: \r\nCode done running.")
                say("Press any key to enter the REPL. Use CTRL-D to reload.")
                mode[0] = "stopped"
            elif mode[0] == "stopped":
                say("\r\nAdafruit CircuitPython (page bridge)\r\n>>> ", end="")
                mode[0] = "repl"
            elif mode[0] == "repl":
                if k in "\r\n":
                    if "s.forget()" in line:
                        saved.forget()
                    say("\r\n>>> ", end="")
                    line = ""
                elif k >= " ":
                    line += k
        if mode[0] == "running":
            h.frame(time.monotonic())
        time.sleep(0.025)


main()

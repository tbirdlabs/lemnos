#!/usr/bin/env python3
# A serial terminal for scripts and tests: resets the board (optional), prints what it sends for a while, and types
# lines into it along the way. Needs pyserial (PlatformIO's Python has it).
#
#   python tools/term.py COM17 --reset --seconds 8
#   python tools/term.py COM17 --seconds 5 --send "status" --send "@2 faketime 2026-11-01T06:59:50Z"
#
# --send TEXT types TEXT and Enter right away; "@N TEXT" waits until N seconds after the start first.
# --dtr for a CircuitPython board (the SCORPIO): it says nothing to a port that hasn't raised DTR. Not for an ESP32
# board, where DTR holds IO0 (the BOOT button) down.

import argparse
import sys
import time

import serial


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--reset", action="store_true", help="pulse EN (RTS) to restart the board first")
    ap.add_argument("--send", action="append", default=[])
    ap.add_argument("--dtr", action="store_true", help="raise DTR (CircuitPython only talks to a port that has)")
    a = ap.parse_args()

    sends = []
    for s in a.send:
        at = 0.0
        if s.startswith("@"):
            head, _, s = s.partition(" ")
            at = float(head[1:])
        sends.append((at, s))
    sends.sort(key=lambda x: x[0])

    port = serial.Serial()                  # set the control lines before opening: on an ESP32 board they're wired to
    port.port = a.port                      # EN and IO0, and opening with them asserted restarts the board
    port.baudrate = a.baud
    port.timeout = 0.05
    port.dtr = a.dtr
    port.rts = False
    port.open()
    if a.reset:
        port.dtr = False                 # IO0 high: boot normally
        port.rts = True                  # EN low
        time.sleep(0.15)
        port.rts = False
    start = time.monotonic()
    out = sys.stdout.buffer
    while True:
        now = time.monotonic() - start
        if now >= a.seconds:
            break
        while sends and sends[0][0] <= now:
            text = sends.pop(0)[1]
            ctrl = {"^C": b"\x03", "^D": b"\x04"}         # CircuitPython: interrupt, soft reload
            port.write(ctrl[text] if text in ctrl else text.encode() + b"\r\n")
        data = port.read(4096)
        if data:
            out.write(data)
            out.flush()
    port.close()


if __name__ == "__main__":
    main()

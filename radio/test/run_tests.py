#!/usr/bin/env python3
# Desktop tests for the radio's portable core: builds test/test_core.c with core/*.c using any C compiler it finds
# (cc/gcc/clang on PATH, else zig via Python: pip install ziglang), runs it, checks every time zone against the
# IANA database (Python's zoneinfo + tzdata) for 2026-2036, and writes test/transcript.txt (a scripted two-player
# session as the radio sends it), which the SCORPIO side's tests replay (circuitpython/tools/test_radio.py).
#
#   py -3 test/run_tests.py
#   py -3 test/run_tests.py --python C:\path\to\python-with-ziglang.exe

import argparse
import datetime
import glob
import os
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
RADIO = os.path.dirname(HERE)
BUILD = os.path.join(os.path.expanduser("~"), ".salient-radio", "test")
EXE = os.path.join(BUILD, "test_core.exe" if os.name == "nt" else "test_core")
SCAN = (2026, 2037)


def compiler(python):
    for cc in ("cc", "gcc", "clang"):
        if shutil.which(cc):
            return [cc]
    for py in [python, os.path.join(os.path.expanduser("~"), ".salient-radio", "hostcc", "Scripts", "python.exe"),
               sys.executable]:
        if py and os.path.exists(py) and subprocess.run([py, "-m", "ziglang", "version"],
                                                         capture_output=True).returncode == 0:
            return [py, "-m", "ziglang", "cc"]
    sys.exit("No C compiler: install gcc or clang, or  pip install ziglang")


def build(cc):
    os.makedirs(BUILD, exist_ok=True)
    src = [os.path.join(HERE, "test_core.c")] + sorted(glob.glob(os.path.join(RADIO, "core", "*.c")))
    cmd = cc + ["-std=c11", "-Wall", "-Wextra", "-Werror", "-O1", "-I", os.path.join(RADIO, "core"), "-o", EXE] + src
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout + r.stderr)
        sys.exit("build failed")


def database_changes(zone, y1, y2):
    """The zone's offset changes as (utc, before, after), from zoneinfo, found the same way as test_core."""
    z = ZoneInfo(zone)

    def off(t):
        return int(datetime.datetime.fromtimestamp(t, z).utcoffset().total_seconds())

    t = int(datetime.datetime(y1, 1, 1, tzinfo=datetime.timezone.utc).timestamp())
    end = int(datetime.datetime(y2, 1, 1, tzinfo=datetime.timezone.utc).timestamp())
    cur = off(t)
    out = [("start", cur)]
    while t < end:
        nxt = off(t + 3600)
        if nxt != cur:
            lo, hi = t, t + 3600
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if off(mid) == cur:
                    lo = mid
                else:
                    hi = mid
            out.append((hi, cur, nxt))
            cur = nxt
        t += 3600
    return out


def check_zones():
    r = subprocess.run([EXE, "--tz-scan", str(SCAN[0]), str(SCAN[1])], capture_output=True, text=True, check=True)
    ours = {}
    for line in r.stdout.splitlines():
        w = line.split()
        if w[1] == "start":
            ours.setdefault(w[0], []).append(("start", int(w[2])))
        else:
            ours.setdefault(w[0], []).append((int(w[1]), int(w[2]), int(w[3])))
    bad = 0
    changes = 0
    for zone, got in ours.items():
        want = database_changes(zone, *SCAN)
        changes += len(want) - 1
        if got != want:
            bad += 1
            diff = [(a, b) for a, b in zip(got, want) if a != b][:2]
            print("FAIL %s: ours %s vs database %s (first differences %s)" % (zone, len(got), len(want), diff))
    print("time zones: %d zones, %d offset changes %d-%d checked to the second against the IANA database, %s"
          % (len(ours), changes, SCAN[0], SCAN[1] - 1, "all match" if not bad else "%d differ" % bad))
    return bad == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", help="a Python with ziglang installed, if there's no C compiler on PATH")
    a = ap.parse_args()
    build(compiler(a.python))
    ok = subprocess.run([EXE]).returncode == 0
    ok = check_zones() and ok
    r = subprocess.run([EXE, "--transcript"], capture_output=True, text=True, check=True)
    with open(os.path.join(HERE, "transcript.txt"), "w", newline="\n") as f:
        f.write(r.stdout)
    print("wrote test/transcript.txt (%d lines)" % len(r.stdout.splitlines()))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# Makes the ready-to-flash files (README.md, "Flashing"), plus SHA256SUMS.txt. For each board:
#   salient-radio-<board>-<version>.bin          first install: bootloader, partition table and firmware in one, at
#                                                0x0. It erases the settings (the gap it fills holds them).
#   salient-radio-<board>-<version>-update.bin   updates: the firmware alone, at 0x10000; keeps the WiFi network,
#                                                settings and paired controllers.
# Run after building every board:
#
#   build                                   (all three boards; build.cmd)
#   py -3 tools/make_release.py             -> dist/
#
# Uses PlatformIO's esptool; the build folder is the one build.cmd uses (%USERPROFILE%\.salient-radio\pio), or
# --build for a plain  pio run  checkout (.pio/build).

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RADIO = os.path.dirname(HERE)
BOARDS = ("esp32dev", "nodemcu-32s", "ttgo-t-display")
HOME = os.path.expanduser("~")


def version():
    m = re.search(r'#define RADIO_FW_VERSION "([^"]+)"', open(os.path.join(RADIO, "shared", "hub.h")).read())
    return m.group(1)


def esptool():
    pio = os.path.join(HOME, ".platformio")
    py = os.path.join(pio, "penv", "Scripts" if os.name == "nt" else "bin", "python.exe" if os.name == "nt" else "python")
    tool = os.path.join(pio, "packages", "tool-esptoolpy", "esptool.py")
    if os.path.exists(py) and os.path.exists(tool):
        return [py, tool]
    return [sys.executable, "-m", "esptool"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default=os.path.join(HOME, ".salient-radio", "pio", "build"))
    ap.add_argument("--pico", default=os.path.join(HOME, ".salient-radio", "pico"))
    a = ap.parse_args()
    ver = version()
    dist = os.path.join(RADIO, "dist")
    os.makedirs(dist, exist_ok=True)
    sums = []
    for board in BOARDS:
        b = os.path.join(a.build, board)
        parts = [("0x1000", os.path.join(b, "bootloader.bin")), ("0x8000", os.path.join(b, "partitions.bin")),
                 ("0x10000", os.path.join(b, "firmware.bin"))]
        missing = [p for _, p in parts if not os.path.exists(p)]
        if missing:
            print("%s: not built (%s); run: build %s" % (board, missing[0], board))
            continue
        out = os.path.join(dist, "salient-radio-%s-%s.bin" % (board, ver))
        cmd = esptool() + ["--chip", "esp32", "merge-bin", "-o", out, "--flash-mode", "dio", "--flash-freq", "40m",
                           "--flash-size", "4MB"]
        for addr, path in parts:
            cmd += [addr, path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stdout + r.stderr)
        update = out[:-4] + "-update.bin"
        shutil.copyfile(parts[2][1], update)
        for f in (out, update):
            sums.append("%s  %s" % (hashlib.sha256(open(f, "rb").read()).hexdigest(), os.path.basename(f)))
            print("%s  (%d KB)" % (f, os.path.getsize(f) // 1024))
    # the Pico W builds, if built (pico/README.md; the folders are the ones used here: --pico)
    for board, folder in (("picow", "build-picow"), ("pico2w", "build-pico2w")):
        uf2 = os.path.join(a.pico, folder, "salient_radio.uf2")
        if os.path.exists(uf2):
            out = os.path.join(dist, "salient-radio-%s-%s.uf2" % (board, ver))
            shutil.copyfile(uf2, out)
            sums.append("%s  %s" % (hashlib.sha256(open(out, "rb").read()).hexdigest(), os.path.basename(out)))
            print("%s  (%d KB)" % (out, os.path.getsize(out) // 1024))
    with open(os.path.join(dist, "SHA256SUMS.txt"), "w", newline="\n") as f:
        f.write("\n".join(sums) + "\n")


if __name__ == "__main__":
    main()

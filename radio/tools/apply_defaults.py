#!/usr/bin/env python3
# Makes sdkconfig.defaults win over an sdkconfig.<board> that already exists. ESP-IDF only applies the defaults to
# options a board's sdkconfig doesn't have yet, so a change to sdkconfig.defaults would otherwise never reach a board
# built before it. build.cmd runs this on its build copy; nothing here uses menuconfig, so the defaults are the truth.
#
#   python tools/apply_defaults.py DIR       (DIR holds sdkconfig.defaults and the sdkconfig.<board> files)

import glob
import os
import re
import sys


def defaults(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        m = re.match(r"(CONFIG_\w+)=(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "."
    want = defaults(os.path.join(d, "sdkconfig.defaults"))
    for path in glob.glob(os.path.join(d, "sdkconfig.*")):
        if path.endswith((".defaults", ".old")):
            continue
        lines = open(path, encoding="utf-8").read().splitlines()
        changed = 0
        for i, line in enumerate(lines):
            m = re.match(r"(CONFIG_\w+)=(.*)$", line) or re.match(r"# (CONFIG_\w+) is not set$", line)
            if not m or m.group(1) not in want:
                continue
            key, value = m.group(1), want[m.group(1)]
            new = "# %s is not set" % key if value == "n" else "%s=%s" % (key, value)
            if line != new:
                lines[i] = new
                changed += 1
        if changed:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(lines) + "\n")
            print("%s: %d setting(s) from sdkconfig.defaults" % (os.path.basename(path), changed))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# Fetches Bluepad32 (with BTstack) at the pinned version and sets them up as ESP-IDF components,
# the way Bluepad32's docs do it by hand (docs/plat_esp32.md: clone, patch BTstack, integrate_btstack.py).
# Only needed to build the firmware; flashing a release needs none of this.
#
#   py -3 tools/get_bluepad32.py            (run again after changing the version below)
#
# Puts them outside the source tree, in ~/.lemnos-radio/bluepad32-<version>/ (or $LEMNOS_RADIO_DEPS): the clone,
# and components/{bluepad32,btstack,cmd_nvs,cmd_system}, which CMakeLists.txt adds to the build. Outside, because the
# source may live on a network share (git won't check out submodules there, and ESP-IDF builds crawl over SMB).

import os
import shutil
import subprocess
import sys

BLUEPAD32_URL = "https://github.com/ricardoquesada/bluepad32.git"
BLUEPAD32_TAG = "4.2.0"            # BTstack comes with it (its submodule), at the commit this tag pins

DEPS = os.path.join(os.environ.get("LEMNOS_RADIO_DEPS") or os.path.join(os.path.expanduser("~"), ".lemnos-radio"),
                    "bluepad32-" + BLUEPAD32_TAG)
CLONE = os.path.join(DEPS, "src")
COMPONENTS = os.path.join(DEPS, "components")
STAMP = os.path.join(COMPONENTS, ".bluepad32-version")

# What integrate_btstack.py copies into the btstack component (BTstack's port/esp32/integrate_btstack.py)
BTSTACK_DIRS = ("src", "3rd-party/bluedroid", "3rd-party/hxcmod-player", "3rd-party/lwip/dhcp-server",
                "3rd-party/lc3-google", "3rd-party/md5", "3rd-party/micro-ecc", "3rd-party/yxml", "platform/freertos",
                "platform/lwip", "tool")
BTSTACK_EMBEDDED = ("hal_time_ms.h", "hal_uart_dma.h", "hci_dump_embedded_stdout.h", "hci_dump_embedded_stdout.c")


def run(*args, cwd=None):
    print("  " + " ".join(args))
    subprocess.check_call(args, cwd=cwd)


def main():
    if os.path.exists(STAMP) and open(STAMP).read().strip() == BLUEPAD32_TAG:
        print("Bluepad32 %s is already set up in %s." % (BLUEPAD32_TAG, COMPONENTS))
        return
    os.makedirs(DEPS, exist_ok=True)
    if os.path.exists(CLONE):
        shutil.rmtree(CLONE, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))
    print("Cloning Bluepad32 %s ..." % BLUEPAD32_TAG)
    run("git", "clone", "--quiet", "--depth", "1", "--branch", BLUEPAD32_TAG, "--recurse-submodules",
        "--shallow-submodules", BLUEPAD32_URL, CLONE)
    btstack = os.path.join(CLONE, "external", "btstack")
    patches = sorted(os.path.join(CLONE, "external", "patches", p)
                     for p in os.listdir(os.path.join(CLONE, "external", "patches")) if p.endswith(".patch"))
    print("Patching BTstack ...")
    for p in patches:
        run("git", "apply", p, cwd=btstack)

    os.makedirs(COMPONENTS, exist_ok=True)
    for name in ("bluepad32", "btstack", "cmd_nvs", "cmd_system"):
        d = os.path.join(COMPONENTS, name)
        if os.path.exists(d):
            shutil.rmtree(d)
    print("Copying components ...")
    for name in ("bluepad32", "cmd_nvs", "cmd_system"):
        shutil.copytree(os.path.join(CLONE, "src", "components", name), os.path.join(COMPONENTS, name))
    dst = os.path.join(COMPONENTS, "btstack")
    shutil.copytree(os.path.join(btstack, "port", "esp32", "components", "btstack"), dst)
    for d in BTSTACK_DIRS:
        shutil.copytree(os.path.join(btstack, d), os.path.join(dst, d))
    emb = os.path.join(dst, "platform", "embedded")
    os.makedirs(emb)
    for f in BTSTACK_EMBEDDED:
        shutil.copy(os.path.join(btstack, "platform", "embedded", f), emb)
    with open(STAMP, "w") as f:
        f.write(BLUEPAD32_TAG + "\n")
    print("Done: Bluepad32 %s in %s." % (BLUEPAD32_TAG, COMPONENTS))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit("Failed: %s" % e)

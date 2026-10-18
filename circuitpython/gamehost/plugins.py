# How config.py names the parts it plugs together: games, LED drivers, input devices and controller hubs.
#
# Each kind has short names for the ones that come with the board ("button", "neopxl8", "i2c", ...). Anything with a
# dot in it is your own, as "module.Name": the module is imported from CIRCUITPY (or lib/) and Name is taken from it.
# So a new input device is a file, say footpedal.py with a class Pedal, and a line in config.py:
#   {"type": "footpedal.Pedal", "pin": "A3"}
# and nothing in the host changes.


def find(name, builtin, what):
    """The thing `name` refers to: builtin[name], or attribute Name of module "module.Name".
    what: a word for the error message ("input type", "LED driver", ...)."""
    if name in builtin:
        return builtin[name]
    if "." not in name:
        raise ValueError("unknown %s %r (built in: %s; or your own as \"module.Name\")"
                         % (what, name, ", ".join(sorted(builtin))))
    k = name.rfind(".")
    mod, attr = name[:k], name[k + 1:]
    return getattr(__import__(mod, None, None, [attr]), attr)

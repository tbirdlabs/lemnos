# LED drivers: what actually sends the colors down the wires. lights.py draws each frame by spot and bar and hands
# it to whichever driver config.LED_DRIVER names; a driver knows nothing about the board's layout.
#
#   "neopxl8"   Adafruit NeoPXL8: 8 outputs at once (the Feather RP2040 SCORPIO's NEOPIXEL0..7). 8 channels.
#   "neopixel"  one strand on one pin, on any CircuitPython board. 1 channel: chain the island and the bars on it.
#   None        no LEDs; the frame is kept in memory only. Desktop Python (no `board` module) always gets this.
#
# Your own (a different LED chip, a screen, a second board over a cable): "module.function" in config.LED_DRIVER,
# called as function(pin, strand, pixel_order, brightness) and returning a pixel object holding a whole number of
# channels of `strand` LEDs each. pin is the board pin config.LED_PIN names (or None).
#
# A pixel object is anything with  obj[i] = (r, g, b),  obj.brightness = 0..1,  obj.show()  and  len(obj).
# Every Adafruit LED library (neopixel, NeoPXL8, DotStar) already is one. LED i of channel c is index c * strand + i.

from . import plugins


def neopxl8(pin, strand, order, brightness):
    import adafruit_neopxl8
    px = adafruit_neopxl8.NeoPxl8(pin, strand * 8, num_strands=8, auto_write=False, brightness=brightness,
                                  pixel_order=order)
    forget_module("adafruit_pioasm", adafruit_neopxl8)   # it only builds the PIO program, once: 10 KB of RAM back
    return px


def forget_module(name, *holders):
    """Unload a library that's done its job, so its RAM comes back: from sys.modules and from the modules holding
    it. Loading it again later reads it afresh."""
    import sys
    sys.modules.pop(name, None)
    for m in holders:
        if hasattr(m, name):
            try:
                delattr(m, name)
            except (AttributeError, TypeError):
                pass


def neopixel(pin, strand, order, brightness):
    import neopixel as lib
    return lib.NeoPixel(pin, strand, auto_write=False, brightness=brightness, pixel_order=order)


DRIVERS = {"neopxl8": neopxl8, "neopixel": neopixel}


def start(name, pin_name, strand, order, brightness):
    """The pixel object for driver `name`, or None for no LEDs (name None, or desktop Python)."""
    if name is None:
        return None
    try:
        import board
    except ImportError:
        return None
    make = plugins.find(name, DRIVERS, "LED driver")
    return make(getattr(board, pin_name) if pin_name else None, strand, order, brightness)

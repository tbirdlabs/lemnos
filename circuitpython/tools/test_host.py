# Desktop test of the board's own parts (gamehost/), with no game's rules involved: the LED maps and placement,
# drivers, effects, the die roller, the board's geometry, controllers coming and going, plug-ins, and the host
# running the example game (games/paint.py), the test pattern (games/testpattern.py) and the clock (games/clock/)
# on a fake clock, the time of day (walltime.py, with a fake RTC chip) and console command lines.
#   py -3 tools/test_host.py          (Island Rush on the board: tools/test_rush.py)

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import config
config.BRIGHTNESS = 1.0                  # these tests read LED values: at full, they're what the game drew
from gamehost import dice, fx, host, hubs, plugins, walltime
from gamehost import geometry as G
from gamehost import lights as leds
from gamehost.controls import ADDED, REMOVED, Controls
from gamehost.game import Game as BaseGame

FAILS = []


def check(name, ok, detail=""):
    if not ok:
        FAILS.append(name)
        print("FAIL", name, detail)


def strip(board, start=None):
    """The island's strip as built, LED by LED from the input, by name: ("line", "A1") or ("hex", "A1", i) with i
    the LED's place in the hex left to right as seen from seat 1. The input is at the corner hex start
    (config.ISLAND_START, as seen from seat 1): its row runs away from that end, and the end of each row loops to
    the same end of the next (line G1 to line F1 on the small board, from G4)."""
    start = start or config.ISLAND_START
    out = []
    rows = "ABCDEFG" if start[0] == "A" else "GFEDCBA"
    for j, row in enumerate(rows):
        n = (4, 5, 6, 7, 6, 5, 4)["ABCDEFG".index(row)]
        run = []
        for k in range(1, n + 1):
            if board == "small":
                run.append(("line", row + str(k)))
            run += [("hex", row + str(k), i) for i in range(3)]
        if board == "small":
            run.append(("line", row + str(n + 1)))
        if (j % 2 == 1) == (start[1] == "1"):
            run.reverse()
        out += run
    return out


def lights_map():
    """Both boards: every island LED where the strip puts it, by name; the bars on their channels."""
    nb = leds.SPOTS * 3                                   # first logical bar LED
    fl = nb + 60                                          # first logical line LED
    check("the default start is G4", leds.layout("large")[3] == leds.layout("large", start="G4")[3])
    for start in leds.STARTS:
        for board, size, nlines in (("large", 111, 0), ("small", 155, 44)):
            isl, nl, strand, ph = leds.layout(board, start=start)
            check("%s: %d island LEDs, %d lines" % (board, size, nlines), (isl, nl, strand) == (size, nlines, size))
            want = strip(board, start)
            got = [None] * size
            for x in want:
                k = G.spot(x[1]) * 3 + x[2] if x[0] == "hex" else fl + G.line(x[1])
                got[ph[k]] = x
            check("%s from the %s: every LED in strip order" % (board, start), got == want,
                  [(i, want[i], got[i]) for i in range(size) if want[i] != got[i]][:3])
            check("%s: seat 1 bar on channel 1" % board, ph[nb] == config.BARS_AT[0][0] * size)
            check("%s: seat 6 bar LED 10" % board, ph[nb + 59] == config.BARS_AT[5][0] * size + 9)

    def at(board, x, start="G4"):
        isl, nl, strand, ph = leds.layout(board, start=start)
        return ph[G.spot(x[1]) * 3 + x[2] if x[0] == "hex" else fl + G.line(x[1])]
    # the same, from the wiring tables in docs/wiring.md
    check("large: G4 is LEDs 2-0, its right LED first", [at("large", ("hex", "G4", i)) for i in range(3)] == [2, 1, 0])
    check("large: F1 follows G1, its left LED first", [at("large", ("hex", "F1", i)) for i in range(3)] == [12, 13, 14])
    check("large: A1 ends the run", at("large", ("hex", "A1", 0)) == 110)
    check("small: line G5 is LED 0, then G4", at("small", ("line", "G5")) == 0 and
          [at("small", ("hex", "G4", i)) for i in range(3)] == [3, 2, 1] and at("small", ("line", "G4")) == 4)
    check("small: line G1 (16) loops to line F1 (17), then F1", at("small", ("line", "G1")) == 16 and
          at("small", ("line", "F1")) == 17 and [at("small", ("hex", "F1", i)) for i in range(3)] == [18, 19, 20])
    check("small: row D is 63-91, from line D1 to line D8", at("small", ("line", "D1")) == 63 and at("small", ("line", "D8")) == 91)
    check("small: A1 and line A1 end the run", at("small", ("hex", "A1", 0)) == 153 and at("small", ("line", "A1")) == 154)
    # from A1 (the old wiring): the whole run reversed
    check("A1: A1 is LEDs 0-2", [at("large", ("hex", "A1", i), "A1") for i in range(3)] == [0, 1, 2])
    check("A1: B5 follows A4, its right LED first", [at("large", ("hex", "B5", i), "A1") for i in range(3)] == [14, 13, 12])
    check("A1: G4 ends the run", at("large", ("hex", "G4", 2), "A1") == 110)
    check("A1 small: line A5 (16) loops to line B6 (17), then B5", at("small", ("line", "A5"), "A1") == 16 and
          at("small", ("line", "B6"), "A1") == 17 and [at("small", ("hex", "B5", i), "A1") for i in range(3)] == [20, 19, 18])
    for board in ("large", "small"):
        a1 = leds.layout(board, start="A1")[3]
        g4 = leds.layout(board, start="G4")[3]
        n = leds.layout(board)[0]
        check("%s: from G4 is from A1 backward" % board, all(g4[k] == n - 1 - a1[k] for k in range(len(a1)) if a1[k] < n))
    try:
        leds.layout("large", start="top")
        check("layout: an unknown start is an error", False)
    except ValueError:
        pass
    # one strand: the bars chained after the island
    chain = tuple((0, 111 + 10 * s) for s in range(6))
    isl, nl, strand, ph = leds.layout("large", (0, 0), chain)
    check("one strand: 171 LEDs", strand == 171, strand)
    check("one strand: every LED once", sorted(ph) == list(range(171)))
    check("one strand: seat 3 bar starts at 131", ph[nb + 20] == 131)
    lt = leds.Lights()
    lt.fill((255, 255, 255))
    lt.show()
    check("power cap dims full white to 4 A", abs(lt.scale * (lt.milliamps() - leds.COUNT) + leds.COUNT - 4000) < 1, lt.scale)


class FakePixels:
    """A pixel object (drivers.py): what a driver hands lights.py."""

    def __init__(self, n):
        self.px = [(9, 9, 9)] * n
        self.brightness = 1.0
        self.shows = 0

    def __len__(self):
        return len(self.px)

    def __setitem__(self, i, c):
        self.px[i] = c

    def show(self):
        self.shows += 1


def driver():
    """lights.py drives any pixel object: dark at start, logical spots and bars land on their wired LEDs."""
    fp = FakePixels(leds.STRAND * 8)
    lt = leds.Lights(fp)
    check("driver: dark at start", all(c == (0, 0, 0) for c in fp.px) and fp.shows == 1)
    lt.spot(G.spot_at(3, -2), [(1, 2, 3), (4, 5, 6), (7, 8, 9)])        # B5: row B runs right (from G4)
    lt.bar(2, [(10, 0, 0)] + [(0, 0, 0)] * 9)
    lt.show()
    b5 = 134 if leds.LINES else 96                        # B5's first LED on the strip: its left one
    check("driver: B5's left light is its first LED", fp.px[b5] == (1, 2, 3) and fp.px[b5 + 2] == (7, 8, 9), fp.px[b5:b5 + 3])
    check("driver: seat 2's LED 1 on channel 2", fp.px[config.BARS_AT[1][0] * leds.STRAND] == (10, 0, 0))
    lt.show()
    check("driver: an unchanged frame isn't sent again", fp.shows == 2, fp.shows)
    steps = [round(leds.step_brightness(n) * 1000) / 10 for n in range(1, 11)]
    check("brightness steps: a log scale, 5 = 10%, 10 = full", steps == [1.6, 2.5, 4.0, 6.3, 10.0, 15.8, 25.1, 39.8,
                                                                       63.1, 100.0], steps)
    lt.set_brightness(0.5)
    lt.show()
    check("driver: brightness dims what the LEDs get, every LED at once", fp.shows == 3 and fp.brightness == 1.0 and
          fp.px[b5 + 2] == (3, 4, 4) and fp.px[config.BARS_AT[1][0] * leds.STRAND] == (5, 0, 0), fp.px[b5:b5 + 3])
    lt.set_brightness(None)
    lt.show()
    check("driver: and back", fp.px[b5 + 2] == (7, 8, 9) and fp.shows == 4)
    try:
        leds.Lights(FakePixels(10))
        check("driver: too few LEDs is an error", False)
    except ValueError:
        pass


def effects():
    """fx.py: one clock, speeds, the flash limit, the time scale, per-LED effects."""
    c = (200, 100, 50)
    a, b = fx.blink(1.0), fx.blink(1.0)
    check("fx: blinks stay in step", all(a.color(c, x / 10) == b.color(c, x / 10) for x in range(30)))
    check("fx: blink on, then off", a.color(c, 0.1) == c and a.color(c, 0.7) == fx.OFF)
    check("fx: no flashing faster than 3 a second", fx.flash(0.1).period >= 1 / 3 and fx.blink(0.05).period >= 1 / 3)
    check("fx: breathe isn't flashing-limited", abs(fx.breathe(0.2).period - 0.2) < 1e-9)
    br = fx.breathe(2, low=0.3)
    lows = [br.color((100, 100, 100), x / 50)[0] for x in range(100)]
    check("fx: breathe stays between low and full", min(lows) >= 29 and max(lows) == 100, (min(lows), max(lows)))
    ch = fx.chase(1.0)
    check("fx: chase starts at LED 1", [ch.color(c, 0.0, i, 10) for i in range(10)] == [c] + [fx.OFF] * 9)
    check("fx: chase reverse starts at LED 10", fx.chase(1.0, reverse=True).color(c, 0.0, 9, 10) == c)
    check("fx: named speeds", (fx.SLOW, fx.NORMAL, fx.FAST) == (3.0, 1.5, 0.6))
    old = getattr(config, "EFFECT_TIME_SCALE", 1.0)
    config.EFFECT_TIME_SCALE = 2.0
    check("fx: time scale slows everything", fx.breathe(1).period == 2.0 and fx.blink(fx.FAST).period == 1.2)
    config.EFFECT_TIME_SCALE = old
    lt = leds.Lights()
    lt.now = 0.7
    lt.spot(0, [c, c, c], [fx.STEADY, fx.blink(1.0), None])
    check("fx: one effect per LED", bytes(lt.raw[0:9]) == bytes(c + fx.OFF + c), list(lt.raw[0:9]))
    lt.bar(1, [c] * 10, fx.chase(1.0))
    b0 = leds.ISLAND * 3
    check("fx: a bar effect sees each LED's place", list(lt.raw[b0 + 21:b0 + 24]) == list(c), list(lt.raw[b0:b0 + 30]))


def roller():
    """dice.py: runs the bar once, then to the result, slowing; holds."""
    for res in (1, 4, 10):
        r = dice.Roll(5.0, res, 10)
        seq = []
        t = 5.0
        while not r.done(t):
            p = r.position(t)
            if not seq or seq[-1] != p:
                seq.append(p)
            t += 0.005
        check("dice: runs 1-10 then to %d" % res, seq == list(range(10)) + list(range(res)), seq)
        frames = 10 + res
        old = sum(0.045 if (frames - i) > 6 else 0.045 + (7 - (frames - i)) * 0.035 for i in range(frames)) + 0.75
        check("dice: timing for %d" % res, abs(r.duration - old) < 1e-9, (r.duration, old))
        check("dice: lands on %d" % res, r.position(r.end - 0.01) == res - 1)
    check("dice: d(6) in range", all(1 <= dice.d(6) <= 6 for _ in range(200)))
    check("dice: seed is 32 bits", all(0 <= dice.seed() < 2 ** 32 for _ in range(20)))
    lt = leds.Lights()
    r = dice.Roll(0.0, 3, 10)
    lt.now = 0.0
    r.draw(lt, 2, [(0, 255, 0)] * 10)
    b = (leds.ISLAND + 10) * 3
    check("dice: draws the light on the bar", bytes(lt.raw[b:b + 6]) == bytes((255, 255, 255, 0, 255, 0)), list(lt.raw[b:b + 6]))


def geometry():
    """The board's shape: rows, neighbors, sides, and every seat's view."""
    check("geometry: 37 spots in rows 4-7-4", [len(r) for r in G.ROWS] == list(G.ROW_LENGTHS) and G.SPOTS == 37)
    check("geometry: A1 is 0, D4 the center, G4 the last", G.name(0) == "A1" and G.name(G.CENTER) == "D4" and G.name(36) == "G4")
    check("geometry: the center has 6 neighbors, corners 3", len(G.neighbors(G.CENTER)) == 6 and len(G.neighbors(0)) == 3)
    check("geometry: neighbors go both ways", all(G.adjacent(n, t) for t in range(G.SPOTS) for n in G.neighbors(t)))
    check("geometry: seat 1 faces row G, left to right", [G.name(t) for t in G.SIDES[1]] == ["G1", "G2", "G3", "G4"])
    check("geometry: seat 4 faces row A, right to left", [G.name(t) for t in G.SIDES[4]] == ["A4", "A3", "A2", "A1"])
    for s in range(1, 7):
        v = G.VIEWS[s]
        check("seat %d: its side is the nearest row" % s, sorted(v.rows[6]) == sorted(G.SIDES[s]))
        check("seat %d: rows 4-7-4" % s, [len(r) for r in v.rows] == [4, 5, 6, 7, 6, 5, 4])
        check("seat %d: reading order" % s, all(v.reading[v.order[t]] == t for t in range(G.SPOTS)))
        ok = True
        for t in range(G.SPOTS):
            for key in ("left", "right", "up", "down"):
                n = v.arrow(t, key)
                ok = ok and (n in (t, G.ON_BAR) or G.adjacent(t, n))
        check("seat %d: an arrow moves to a neighbor (or the bar)" % s, ok)
        p = v.path(v.rows[0][0], G.ON_BAR)
        check("seat %d: a path from the far corner to the bar" % s, p and p[-1] == G.ON_BAR, p)
    check("geometry: seat 1's view is the numbering", all(G.VIEWS[1].row[t] == G.ROW[t] for t in range(G.SPOTS)))


def names():
    """Hexes and lines by name: rows A-G, hexes 1 to n and lines 1 to n+1, left to right as seen from seat 1."""
    check("names: every hex", [G.name(t) for t in range(G.SPOTS)] ==
          [r + str(k) for r, n in zip("ABCDEFG", G.ROW_LENGTHS) for k in range(1, n + 1)])
    check("names: every line", [G.line_name(k) for k in range(G.LINES)] ==
          [r + str(k) for r, n in zip("ABCDEFG", G.ROW_LENGTHS) for k in range(1, n + 2)] and G.LINES == 44)
    check("names: both ways", all(G.spot(G.name(t)) == t for t in range(G.SPOTS)) and
          all(G.line(G.line_name(k)) == k for k in range(G.LINES)))
    check("names: lower case, and numbers pass through", G.spot("d4") == G.CENTER and G.spot(5) == 5 and G.line(7) == 7)
    for bad in ("A5", "H1", "B0", "", "D"):
        try:
            G.spot(bad)
            check("names: no hex %r" % bad, False)
        except (ValueError, IndexError):
            pass
    try:
        G.line("B7")
        check("names: no line B7", False)
    except ValueError:
        pass
    check("lines: hex B3 is between lines B3 and B4",
          G.line_name(G.left_line("B3")) == "B3" and G.line_name(G.right_line("B3")) == "B4")
    check("lines: between, either order", G.line_name(G.between("B3", "B4")) == "B4" == G.line_name(G.between("B4", "B3")))
    check("lines: the ends touch one hex", [G.name(t) for t in G.line_spots("B1")] == ["B1"] and
          [G.name(t) for t in G.line_spots("B6")] == ["B5"])
    check("lines: the others touch two", [G.name(t) for t in G.line_spots("D4")] == ["D3", "D4"])
    for a, b in (("B3", "B5"), ("B3", "C3"), ("B3", "B3")):
        try:
            G.between(a, b)
            check("lines: nothing between %s and %s" % (a, b), False)
        except ValueError:
            pass


def use_board(board):
    """Rebuild lights.py's LED map for a board; returns the board it had."""
    import importlib
    old = config.BOARD
    config.BOARD = board
    importlib.reload(leds)
    return old


def small_board():
    """On the small board, names land on the right LEDs: row B runs left to right from LED 117 (line B1) to 137."""
    old = use_board("small")
    try:
        fp = FakePixels(leds.STRAND * 8)
        lt = leds.Lights(fp)
        check("small: has lines", lt.has_lines and leds.STRAND == 155)
        red, green = (9, 0, 0), (0, 9, 0)
        lt.line("B1", red)
        lt.between("B3", "B4", green)
        lt.spot("B3", [(1, 1, 1), (2, 2, 2), (3, 3, 3)])
        lt.show()
        check("small: line B1 (row B's left end) is LED 117", fp.px[117] == red)
        check("small: between B3 and B4 is LED 129", fp.px[129] == green)
        check("small: hex B3 is LEDs 126, 127, 128, left to right", fp.px[126:129] == [(1, 1, 1), (2, 2, 2), (3, 3, 3)], fp.px[124:130])
        check("small: nothing else lit", sum(1 for c in fp.px if c != (0, 0, 0)) == 5)
        # the example game joins same-colored hexes with their lines
        paint = host.load_game("paint")(host.Board(lt, Controls(hardware=False)))
        for name in ("B4", "B5", "D1"):
            paint.paint[G.spot(name)] = red
        paint.paint[G.spot("D2")] = green
        lt.fill(leds.OFF)
        paint.draw(lt, 0.0)
        lit = [G.line_name(k) for k in range(G.LINES) if any(lt.raw[(leds.FIRST_LINE + k) * 3:(leds.FIRST_LINE + k) * 3 + 3])]
        check("paint: lines join same colors, and edge painted row ends", lit == ["B5", "B6", "D1"], lit)
    finally:
        use_board(old)
    old = use_board("large")
    try:
        lt = leds.Lights(FakePixels(leds.STRAND * 8))
        lt.line("B1", (9, 9, 9))
        lt.between("B3", "B4", (9, 9, 9))
        check("large: no lines, and drawing them does nothing", not lt.has_lines and not any(lt.raw))
    finally:
        use_board(old)


def controllers():
    """Controllers arrive (once), go away and come back; actions come out in order."""
    ctl = Controls(hardware=False)
    a = ctl.get("x", "pad", None, ("move", "pick"))
    check("controls: same id, same controller", ctl.get("x", "pad", None, ()) is a)
    check("controls: added once", ctl.take_notices() == [(ADDED, a)])
    ctl.feed(a, "move")
    ctl.feed(a, "pick")
    check("controls: actions in order", ctl.poll(0.0) == [(a, "move"), (a, "pick")] and ctl.poll(0.1) == [])
    ctl.remove(a)
    ctl.remove(a)
    check("controls: removed once", ctl.take_notices() == [(REMOVED, a)] and not a.connected and ctl.connected() == [])
    ctl.get("x", "pad", None, ())
    check("controls: back again", ctl.take_notices() == [(ADDED, a)] and a.connected)
    check("controls: find", ctl.find("x") is a and ctl.find("y") is None)


def held_buttons():
    """A wired button held MENU_HOLD_S gives menu, after whatever it gave first; letting go gives nothing more."""
    from gamehost import inputs

    class Pin:
        value = True                                  # pulled up: not pressed

    pin = Pin()
    real = inputs._switch
    inputs._switch = lambda name: pin
    try:
        for spec, first in (({"pin": "X", "does": "back"}, ["back"]),
                            ({"pin": "X", "does": "pick", "hold": "back"}, ["back"])):
            b = inputs.Button(spec)
            got = []
            pin.value = True
            b.poll(0.0, got.append)
            pin.value = False                         # pressed, and held
            for t in (0.01, 0.05, 1.0, inputs.MENU_HOLD_S - 0.1):
                b.poll(t, got.append)
            check("button %s: before the long hold" % spec["does"], got == first, got)
            b.poll(inputs.MENU_HOLD_S + 0.1, got.append)
            b.poll(inputs.MENU_HOLD_S + 0.5, got.append)
            check("button %s: held long, menu once" % spec["does"], got == first + ["menu"], got)
            pin.value = True
            b.poll(inputs.MENU_HOLD_S + 1.0, got.append)
            check("button %s: let go, nothing more" % spec["does"], got == first + ["menu"], got)
            check("button %s: can menu" % spec["does"], "menu" in b.can)
    finally:
        inputs._switch = real


def plug_ins():
    """config names built-ins by short name and your own as module.Name."""
    check("plugins: built in", plugins.find("button", {"button": int}, "input type") is int)
    check("plugins: your own", plugins.find("games.paint.Game", {}, "game") is host.load_game("paint"))
    try:
        plugins.find("buton", {"button": int}, "input type")
        check("plugins: a typo is an error", False)
    except ValueError as e:
        check("plugins: the error names the built-ins", "button" in str(e), e)


class Recorder(BaseGame):
    """A game that only records what the host tells it."""

    def __init__(self, board):
        BaseGame.__init__(self, board)
        self.log = []

    def controller_added(self, c, now):
        self.log.append(("added", c.id))

    def controller_removed(self, c, now):
        self.log.append(("removed", c.id))

    def event(self, c, a, now):
        self.log.append((c.id, a))

    def update(self, now):
        self.log.append("update")

    def draw(self, lights, now):
        lights.spot(0, [(5, 5, 5)] * 3)


def hosting():
    """The host's frame: arrivals first, then actions, update, then a fresh drawing; and the example game runs."""
    h = host.Host(Recorder, host.Board(leds.Lights(), Controls(hardware=False)))
    ctl = h.board.controls
    c = ctl.get("k", "keys", 2, ("move", "pick"))
    ctl.feed(c, "move")
    h.frame(1.0)
    check("host: added, then the action, then update", h.game.log == [("added", "k"), ("k", "move"), "update"], h.game.log)
    check("host: drew and showed", h.board.lights.sent[0] == 5 and h.board.lights.now == 1.0)
    check("host: board.controllers", h.board.controllers == [c])
    ctl.remove(c)
    h.frame(1.1)
    check("host: removed", h.game.log[-2:] == [("removed", "k"), "update"], h.game.log)
    check("host: load_game, a file", host.load_game("paint").__module__ == "games.paint")
    # the example game, through the host
    h = host.Host(host.load_game("paint"), host.Board(leds.Lights(), Controls(hardware=False)))
    ctl = h.board.controls
    one = ctl.get("one", "one switch", 4, ("move", "pick"))
    pad = ctl.get("pad", "d-pad", None, ("up", "down", "left", "right", "pick", "back"))
    h.frame(0.0)
    g = h.game
    check("paint: a cursor each, on its side", g.players[one].cursor == G.SIDES[4][1] and g.players[pad].cursor == G.SIDES[1][1])
    for a in ("move", "move", "pick"):
        ctl.feed(one, a)
    for a in ("up", "pick", "left", "pick"):
        ctl.feed(pad, a)
    h.frame(0.1)
    painted = [t for t in range(G.SPOTS) if g.paint[t]]
    check("paint: three spots painted", len(painted) == 3, [G.name(t) for t in painted])
    b4 = (leds.ISLAND + 30) * 3                           # seat 4, LED 1
    check("paint: seat 4's bar shows 1", any(h.board.lights.sent[b4:b4 + 3]) and not any(h.board.lights.sent[b4 + 3:b4 + 6]))
    ctl.feed(pad, "back")
    h.frame(0.2)
    check("paint: back clears your own", sum(1 for t in range(G.SPOTS) if g.paint[t]) == 1)
    ctl.remove(pad)
    h.frame(0.3)
    check("paint: a controller that leaves loses its cursor", pad not in g.players)


def carried_bars():
    """A bar built into a controller goes with it: lights.carry swaps seats' bars, and the lobby takes a carried bar
    to the seat its player picks (Island Rush's seat field), so the bar in their hands shows their seat."""
    lt = leds.Lights()
    first = lambda n: leds.ISLAND + (n - 1) * leds.BAR      # bar n's LED 1, logically

    def on(n):
        return lt.raw[first(n) * 3] == 10

    lt.carry({4: 1})
    lt.bar(4, [(10, 0, 0)] * leds.BAR)
    check("carry: seat 4 drawn on bar 1", on(1) and not on(4))
    lt.fill(leds.OFF)
    lt.bar(1, [(10, 0, 0)] * leds.BAR)
    check("carry: and seat 1 on bar 4", on(4) and not on(1))
    lt.fill(leds.OFF)
    lt.bar_at(1, [(10, 0, 0)] * leds.BAR)
    check("carry: bar_at draws by place", on(1) and not on(4))
    lt.carry({2: 1, 3: 2})
    check("carry: two at once, the others keep their own", lt.seat_bar == [3, 1, 2, 4, 5, 6], lt.seat_bar)
    lt.carry({3: 2, 2: 1})
    check("carry: in any order", lt.seat_bar == [3, 1, 2, 4, 5, 6], lt.seat_bar)
    lt.carry({})
    check("carry: none, all their own", lt.seat_bar == [1, 2, 3, 4, 5, 6])
    # through the host and the lobby
    h = host.Host(host.load_game("rush"), host.Board(leds.Lights(), Controls(hardware=False)))
    ctl = h.board.controls
    w = ctl.get("w", "wired", 1, ("move", "move_back", "pick", "back"))
    w.bar = 1
    pad = ctl.get("pad", "pad", None, ("move", "pick", "back"))
    h.frame(0.0)
    lob = h.lobby
    check("lobby: a carried bar at its own seat", h.board.lights.seat_bar == [1, 2, 3, 4, 5, 6], h.board.lights.seat_bar)
    ctl.feed(w, "pick")                                   # join, then choose a seat
    h.frame(0.1)
    t = 0.1
    for _ in range(8):
        if lob.choices.get("seat:w") == "4":
            break
        ctl.feed(w, "move")
        t += 0.1
        h.frame(t)
    check("lobby: seat 4 chosen", lob.choices.get("seat:w") == "4", lob.choices)
    m = h.board.lights.seat_bar
    check("lobby: the controller's bar shows seat 4, and bar 4 seat 1", m[3] == 1 and m[0] == 4, m)
    check("lobby: its field is drawn on its own bar", any(h.board.lights.raw[first(1) * 3:(first(1) + leds.BAR) * 3]))
    ctl.feed(pad, "pick")                                 # a controller without a bar changes nothing
    h.frame(t + 0.1)
    check("lobby: a controller without a bar", h.board.lights.seat_bar[3] == 1, h.board.lights.seat_bar)
    ctl.feed(w, "back")
    ctl.feed(w, "back")
    h.frame(t + 0.2)
    check("lobby: left, the bar's back at its own seat", w not in lob.joined and h.board.lights.seat_bar[0] == 1,
          (lob.joined, h.board.lights.seat_bar))
    # set up on the USB page instead: the seat chosen there
    msg = h.apply("setup", {"players": "2", "seat:w": "4", "seat:pad": "out"}, t + 0.3)
    h.frame(t + 0.4)
    m = h.board.lights.seat_bar
    check("page: started at seat 4", msg is None and lob.state == "play" and lob.joined == [w], (msg, lob.state))
    check("page: the controller's bar shows seat 4", m[3] == 1 and m[0] == 4, m)


def forest_fire():
    """games/fire/ through the host: the forest grows and burns on its own, pick calls down lightning (once a
    second at most), and every bar shows the forest and the fire."""
    import random
    from games.fire import game as F
    random.seed(5)
    h = host.Host(host.load_game("fire"), host.Board(leds.Lights(), Controls(hardware=False)))
    ctl = h.board.controls
    c = ctl.get("k", "keys", 1, ("move", "pick"))
    g = h.game
    t = 0.0
    burned = green = False
    for _ in range(2400):                                 # two minutes at 20 frames a second
        t += 0.05
        h.frame(t)
        trees, burning = g.forest.cover()
        burned = burned or burning > 0
        raw = h.board.lights.raw
        green = green or any(raw[k * 3 + 1] > 60 and raw[k * 3] < 60 for k in range(leds.ISLAND))
    check("fire: the forest shows", green)
    check("fire: a fire in two minutes on its own", burned)
    while not g.forest.cover()[0]:                        # (some forest to strike)
        t += F.TICK_S
        h.frame(t)
    before = sum(1 for x in g.forest.fire if x)
    ctl.feed(c, "pick")
    ctl.feed(c, "pick")
    h.frame(t + 0.01)
    after = sum(1 for x in g.forest.fire if x)
    check("fire: pick strikes, once", after == before + 1, (before, after))
    raw = h.board.lights.raw
    b1 = leds.ISLAND * 3
    check("fire: the bars show it", any(raw[b1:b1 + leds.BAR * 3]))
    f = F.Forest(random.Random(1))
    f.tree = [3] * G.SPOTS
    f.strike(G.CENTER)
    for _ in range(60):
        f.step()
    check("fire: a fire in thick forest spreads", sum(1 for x in f.tree if x == 3) < G.SPOTS - 6)



def fireflies():
    """games/fireflies/ through the host, on both boards: an evening starts with one firefly, the next answers it
    from near it just after it glows, more come out until all are, and they fall into step on their own; glows are
    single LEDs (line LEDs too, on the small board), never faster than the flash limit; pick starts the evening
    over."""
    import random
    from games.fireflies import game as F
    random.seed(3)
    h = host.Host(host.load_game("fireflies"), host.Board(leds.Lights(), Controls(hardware=False)))
    g = h.game
    t = 0.0
    lit = 0
    for _ in range(200):                                  # 10 s at 20 frames a second
        t += 0.05
        h.frame(t)
        lit = max(lit, sum(1 for k in range(leds.ISLAND) if h.board.lights.raw[k * 3 + 1]))
    check("fireflies: dusk, one alone", g.swarm.count_out() == 1 and lit == 1, (g.swarm.count_out(), lit))
    check("fireflies: never quicker than the flash limit", F.RISE + F.FADE < F.PERIOD * (1 - F.SPREAD) and
          1 / (F.PERIOD * (1 - F.SPREAD)) <= fx.MAX_FLASHES_PER_S)
    sw = F.Swarm(False, random.Random(2))
    now = 0.0
    first = [f for f in range(len(sw.at)) if sw.out[f]][0]
    while sw.count_out() < 2 and now < 60:
        now += 0.025
        sw.run(now, 0.025)
    two = [f for f in range(len(sw.at)) if sw.out[f] and f != first]
    check("fireflies: a second one answers", two and now >= F.FIRST_ANSWER_S, now)
    if two:
        a = two[0]
        check("fireflies: from near the first", sw.dist(sw.at[a], sw.at[first]) <= F.NEAR)
        while sw.lit[a] < 0 and now < 70:
            now += 0.025
            sw.run(now, 0.025)
        gap = sw.lit[a] - sw.lit[first]
        check("fireflies: just after it glows", F.ANSWER_AFTER[0] - 0.1 <= gap <= F.ANSWER_AFTER[1] + 0.1, gap)
    while sw.part == "dusk" and now < 600:
        now += 0.05
        sw.run(now, 0.05)
    check("fireflies: all out in a few minutes", sw.part != "dusk" and sw.count_out() == len(sw.at) and
          120 < now < 300, (sw.part, now))
    while sw.part == "gathering" and now < 2400:
        now += 0.05
        sw.run(now, 0.05)
    check("fireflies: in step on their own", sw.part == "night", (sw.part, now))
    while sw.part != "dusk" and now < 3000:
        now += 0.05
        sw.run(now, 0.05)
    check("fireflies: out one by one, dark, then a new evening", sw.part == "dusk" and sw.evenings == 2 and
          sw.count_out() == 1, (sw.part, sw.evenings))
    for _ in range(4000):                                 # (on into the next evening)
        t += 0.05
        h.frame(t)
    h.board.controls.feed(h.board.controls.get("k", "keys", 1, ("pick",)), "pick")
    h.frame(t + 0.05)
    check("fireflies: pick starts the evening over", g.swarm.part == "dusk" and g.swarm.count_out() == 1)
    small = F.Swarm(True, random.Random(1))
    check("fireflies: the small board's line LEDs are places too", len(small.places) == 155 and
          any(small.places[p][0] is None for p in range(len(small.places))))


def aurora():
    """games/aurora/ through the host, on both boards: a faint quiet sky, a display building to a peak and
    fading, pick sets off a surge, the bars show the activity, and nothing jumps: every LED changes gradually."""
    import random
    from games.aurora import game as A
    for lines in (False, True):
        sky = A.Sky(lines, random.Random(4))
        name = "aurora (%s)" % ("small" if lines else "large")
        quiet = sky.colors()
        check(name + ": a quiet sky, faint", 0 < max(max(c) for c in quiet) < 60, max(max(c) for c in quiet))
        now, dt = 0.0, 1.0 / A.DRAW_HZ
        parts = []
        worst = 0
        before = quiet
        while now < 700:
            now += dt
            sky.run(now, dt)
            if not parts or parts[-1] != sky.part:
                parts.append(sky.part)
            after = sky.colors()
            worst = max(worst, max(abs(a[i] - b[i]) for a, b in zip(before, after) for i in range(3)))
            before = after
        check(name + ": quiet, build, peak, fade, quiet", parts[:5] == ["quiet", "build", "peak", "fade", "quiet"], parts)
        rate = worst * A.DRAW_HZ                          # the fastest any LED changes, levels a second
        check(name + ": every change gradual (dark to full in 0.2 s at the quickest: slower than the flash limit)",
              rate < 1200, rate)
    h = host.Host(host.load_game("aurora"), host.Board(leds.Lights(), Controls(hardware=False)))
    c = h.board.controls.get("k", "keys", 1, ("pick",))
    for k in range(40):
        h.frame(k * 0.05)
    a0 = h.game.sky.activity()
    h.board.controls.feed(c, "pick")
    for k in range(40, 80):
        h.frame(k * 0.05)
    g = h.game.sky
    check("aurora: pick, a surge (swelling) and a display", g.surge > 0.5 and g.part == "build" and g.activity() > a0,
          (g.surge, g.part))
    b1 = leds.ISLAND * 3
    check("aurora: the bars show it", any(h.board.lights.raw[b1:b1 + leds.BAR * 3]))


def rain():
    """games/rain/, on both boards: a ring reaches every LED by distance and fades; a shower goes still, build,
    pour, ease, still; pick drops a pebble (twice a second at most); the bars show the rain; nothing jumps."""
    import random
    from games.rain import game as R
    for lines in (False, True):
        name = "rain (%s)" % ("small" if lines else "large")
        pond = R.Pond(lines, random.Random(2))
        n = pond.n
        check(name + ": each hex has every LED, nearest first", all(sorted(o) == list(range(n)) for o in pond.order) and
              all(list(d) == sorted(d) for d in pond.dist))
        still = pond.colors(0.0)
        check(name + ": a still pond, faint", all(c == R.COLORS[0] for c in still))
        pond.rings = [[G.CENTER, 0.0, 1.0, R.LIFE, True]]
        reached = set()
        for k in range(1, int(R.LIFE * 20)):
            reached |= {i for i, c in enumerate(pond.colors(k / 20)) if c != R.COLORS[0]}
        check(name + ": one ring from the middle reaches every LED", len(reached) == n, (len(reached), n))
        check(name + ": and is gone when it's done", all(c == R.COLORS[0] for c in pond.colors(R.LIFE)))
        pond = R.Pond(lines, random.Random(5))
        now, dt = 0.0, 1.0 / R.DRAW_HZ
        parts, worst, before = [], 0, pond.colors(0.0)
        while now < 600:
            now += dt
            pond.run(now, dt)
            if not parts or parts[-1] != pond.part:
                parts.append(pond.part)
            after = pond.colors(now)
            worst = max(worst, max(abs(a[i] - b[i]) for a, b in zip(before, after) for i in range(3)))
            before = after
        check(name + ": build, pour, ease, still, build (a shower from the start)",
              parts[:5] == ["build", "pour", "ease", "still", "build"], parts)
        check(name + ": it rained", pond.drops > 50, pond.drops)
        check(name + ": every change gradual (dark to full in 0.2 s at the quickest)", worst * R.DRAW_HZ < 1300,
              worst * R.DRAW_HZ)
    h = host.Host(host.load_game("rain"), host.Board(leds.Lights(), Controls(hardware=False)))
    c = h.board.controls.get("k", "keys", 1, ("pick",))
    h.frame(0.0)
    n0 = h.game.pond.drops
    for _ in range(3):
        h.board.controls.feed(c, "pick")
    h.frame(0.05)
    check("rain: pick drops a pebble, once", h.game.pond.drops == n0 + 1, h.game.pond.drops - n0)
    p = h.game.pond
    p.to("pour", 0.1)
    p.peak = R.PEAK[1]
    p.lasts = 1e9
    for k in range(3, 40):
        h.frame(k * 0.05)
    b1 = leds.ISLAND * 3
    check("rain: the bars show it", any(h.board.lights.raw[b1:b1 + leds.BAR * 3]))


def test_pattern():
    """games/testpattern.py on both boards, through the host to a pixel object: red lights the LEDs one at a time,
    in place order (rows A-G left to right as seen from seat 1, then bars 1-6 LED 1-10), each on the strip address
    the wiring tables give; then green over it, then blue; pause, step, start over."""
    cap = config.POWER_LIMIT_A
    config.POWER_LIMIT_A = None          # full red on the small board is over 4 A: the LEDs would get it dimmed
    for board in ("large", "small"):
        old = use_board(board)
        try:
            fp = FakePixels(leds.STRAND * 8)
            h = host.Host(host.load_game("testpattern"), host.Board(leds.Lights(fp), Controls(hardware=False)))
            run = strip(board)
            want = []
            for r, n in enumerate(G.ROW_LENGTHS):
                row = "ABCDEFG"[r]
                for k in range(1, n + 1):
                    if board == "small":
                        want.append(run.index(("line", row + str(k))))
                    want += [run.index(("hex", row + str(k), i)) for i in range(3)]
                if board == "small":
                    want.append(run.index(("line", row + str(n + 1))))
            want += [config.BARS_AT[s][0] * leds.STRAND + config.BARS_AT[s][1] + i for s in range(6) for i in range(10)]
            used = set(want)
            t = 0.0
            for color in ((255, 0, 0), (0, 255, 0), (0, 0, 255)):
                order = []
                for _ in range(len(want) * 3 + 200):
                    t += 0.025
                    h.frame(t)
                    order += [i for i in used if fp.px[i] == color and i not in order]
                    if len(order) == len(want) and h.game.done == 0:
                        break
                check("%s pattern: %s lights in place order" % (board, color), order == want,
                      [(i, want[i], order[i]) for i in range(min(len(want), len(order))) if want[i] != order[i]][:3])
                check("%s pattern: the board all %s" % (board, color), all(fp.px[i] == color for i in used))
                check("%s pattern: nothing else lit" % board,
                      all(fp.px[i] == (0, 0, 0) for i in range(len(fp.px)) if i not in used))
            g = h.game
            ctl = h.board.controls
            c = ctl.get("k", "keys", 1, ("move", "move_back", "pick", "back"))
            ctl.feed(c, "pick")
            h.frame(t + 0.1)
            at = g.done
            h.frame(t + 2.0)
            check("%s pattern: pick pauses" % board, g.paused and g.done == at)
            for a in ("move", "move", "move_back"):
                ctl.feed(c, a)
            h.frame(t + 2.1)
            check("%s pattern: steps while paused" % board, g.done == at + 1, (at, g.done))
            ctl.feed(c, "back")
            h.frame(t + 2.2)
            check("%s pattern: back starts over from dark" % board, g.done == 0 and not g.paused and
                  all(fp.px[i] == (0, 0, 0) for i in used))
        finally:
            use_board(old)
    config.POWER_LIMIT_A = cap


class FakeChip:
    """An RTC chip whose seconds tick over at a set point of the fake nanosecond clock."""

    def __init__(self, clock, t, lost=False):
        self.clock = clock               # [ns]
        self.t0 = t                      # (y, mo, d, h, mi, s) at ns 0
        self.lost = lost
        self.written = None

    def read(self):
        if self.lost:
            return None
        y, mo, d, h, mi, s = self.t0
        n = (h * 3600 + mi * 60 + s) + self.clock[0] // 1000000000
        return (y, mo, d, n // 3600 % 24, n // 60 % 60, n % 60)

    def write(self, t, wday):
        self.written = (t, wday)
        self.lost = False


def wall_time():
    """walltime: set and read back, typed commands, and keeping in step with an RTC chip."""
    clock = [0]
    w = walltime.Wall(chip=None, ns=lambda: clock[0], board_rtc=None)
    check("wall: not known at first", not w.known and "(not set)" in w.describe())
    w.set(23, 59, 58)
    clock[0] += 3500000000
    check("wall: runs and wraps at midnight", w.hms() == (0, 0, 1) and w.ms() == 1500, (w.hms(), w.ms()))
    for text, want in (("time 14:32", (14, 32, 0)), ("TIME 2:32pm", (14, 32, 0)), ("time 12:05 am", (0, 5, 0)),
                       ("t 9:07:30", (9, 7, 30)), ("time 2026-10-20 14:32:05", (14, 32, 5))):
        reply = w.command(text)
        check("wall: %r" % text, w.hms() == want and reply.startswith("Set"), (w.hms(), reply))
    check("wall: time alone says it", "14:32:05" in w.command("time"))
    for bad in ("time 25:00", "time 13:00pm", "time noon", "time 2026-13-01 1:00"):
        check("wall: %r refused" % bad, w.command(bad).startswith("Type") and w.hms() == (14, 32, 5), w.command(bad))
    check("wall: not a time command", w.command("help") is None)
    check("wall: weekday", walltime.weekday(2026, 10, 20) == 1 and walltime.weekday(2000, 1, 1) == 5)
    # a chip: read at start, starting the milliseconds where its seconds tick over
    clock[0] = 300000000                 # 0.3 s: the chip's next tick is at 1 s
    chip = FakeChip(clock, (2026, 10, 20, 8, 15, 0))
    w = walltime.Wall(chip=chip, ns=lambda: clock[0], board_rtc=None)
    while clock[0] < 1500000000:
        w.update()
        clock[0] += 25000000
    check("wall: from the chip, on its tick", w.known and w.chip_ok and
          abs(w.ms() - (8 * 3600 + 15 * 60 + 1.5) * 1000) <= 25, (w.ms(), w.describe()))
    w.set(9, 0, 0, (2026, 10, 21))
    check("wall: setting writes the chip", chip.written == ((2026, 10, 21, 9, 0, 0), 2), chip.written)
    clock[0] = 0
    w = walltime.Wall(chip=FakeChip(clock, (2026, 1, 1, 0, 0, 0), lost=True), ns=lambda: clock[0], board_rtc=None)
    for _ in range(10):
        w.update()
        clock[0] += 25000000
    check("wall: a chip that lost the time isn't trusted", not w.known and w.chip_ok is False, w.describe())


class FakeSerial:
    def __init__(self):
        self.text = ""
        self.runtime = self

    @property
    def serial_bytes_available(self):
        return len(self.text)

    def read(self, n):
        out = self.text[:n]
        self.text = self.text[n:]
        return out


def console():
    """The console hub: keys are actions; a line starting with another letter (or /) is a command for the game."""
    ctl = Controls(hardware=False)
    ser = FakeSerial()
    con = hubs.Console(ctl, sup=ser, stdin=ser)
    got = []
    ser.text = "mp2ptime 14:3x\b2\r/settime 1:00\rb"
    con.poll(0.0, lambda c, a: got.append((c.id, a)))
    check("console: keys", got == [("console1", "move"), ("console1", "pick"), ("console2", "pick"), ("console2", "back")], got)
    check("console: commands", ctl.take_commands() == ["time 14:32", "settime 1:00"])


def clock():
    """games/clock/: the hands point at the time, the corners stay dark, the ring shows the hours, the minute and
    the second; pick turns the second light off; "time" commands reach it through the host."""
    from games.clock import game as C
    config_rtc = getattr(config, "RTC", None)
    config.RTC = None
    ns = [0]
    try:
        for board in ("large", "small"):
            old = use_board(board)
            try:
                lt = leds.Lights()
                h = host.Host(host.load_game("clock"), host.Board(lt, Controls(hardware=False)))
                g = h.game
                g.wall = walltime.Wall(chip=None, ns=lambda: ns[0], board_rtc=None)
                g.wall.set(3, 0, 30)
                h.frame(0.0)

                def lit(color):
                    """{row letter: the hexes (and lines, as "|B4") lit in this color, left to right}"""
                    out = {}
                    for t in range(G.SPOTS):
                        for i in range(3):
                            if g.spot_colors[t][i] == color:
                                out.setdefault("ABCDEFG"[G.ROW[t]], []).append(G.name(t))
                    for k, c in enumerate(g.line_colors):
                        if c == color:
                            out.setdefault("ABCDEFG"[G.LINE_ROW[k]], []).append("|" + G.line_name(k))
                    return out
                hour = lit(C.HOUR)
                check("%s clock: the hour hand at 3, along row D" % board,
                      list(hour) == ["D"] and set(n for n in hour["D"] if n[0] != "|") == {"D5", "D6"}, hour)
                minute = lit(C.MINUTE)
                check("%s clock: the minute hand at 12, one LED in each row above the center" % board,
                      sorted(minute) == ["A", "B", "C"] and all(len(v) == 1 for v in minute.values()) and minute["B"] == ["B3"], minute)
                second = lit(C.SECOND)
                check("%s clock: the second hand at 6 (30 s), one LED in each row below" % board,
                      sorted(second) == ["E", "F", "G"] and all(len(v) == 1 for v in second.values()) and second["F"] == ["F3"], second)
                check("%s clock: the center is the hub" % board, g.spot_colors[G.CENTER] == [C.HUB] * 3)
                corners = [G.name(t) for t in range(G.SPOTS) if g.spot_colors[t] == [C.OFF] * 3]
                check("%s clock: the 6 corners dark" % board, sorted(corners) == ["A1", "A4", "D1", "D7", "G1", "G4"], corners)
                g.wall.set(12, 0, 0)             # all three up: they mix
                h.frame(0.01)
                mixed = lit((255, 255, 255))
                check("%s clock: at 12:00:00 the hands add to white where all three are" % board,
                      sorted(mixed) == ["B", "C"] and mixed["B"] == ["B3"], mixed)
                check("%s clock: and to yellow (minute + second) past the hour hand's tip" % board,
                      list(lit((255, 255, 0))) == ["A"] and not lit(C.HOUR) and not lit(C.MINUTE) and not lit(C.SECOND))
                g.wall.set(3, 0, 30)
                ns[0] += 15000000000             # 15 s on: the second hand at 9, along row D (as far out as at 12:
                                                 # into corner D1's inner LED)
                h.frame(0.05)
                second = lit(C.SECOND)
                check("%s clock: the second hand at 9, along row D" % board,
                      list(second) == ["D"] and set(n for n in second["D"] if n[0] != "|") == {"D1", "D2", "D3"}, second)
                check("%s clock: the hour hand still at 3" % board, set(n for n in lit(C.HOUR)["D"] if n[0] != "|") == {"D5", "D6"})
                ns[0] -= 15000000000
                ring = g.ring(g.wall.ms())
                check("%s clock: ring light 0 is the top bar's LED 5, then clockwise" % board,
                      C.RING_AT[0] == (4, 4) and C.RING_AT[5] == (5, 9) and C.RING_AT[30] == (1, 4) and C.RING_AT[59] == (4, 5))
                check("%s clock: second light at the bottom (30 s)" % board, ring[29][0] > 100 and ring[30][0] > 100, ring[28:32])
                h.frame(0.1)
                bar1 = (leds.ISLAND + 4) * 3
                check("%s clock: drawn on seat 1's bar" % board, lt.sent[bar1] > 100, lt.sent[bar1:bar1 + 3])
                ctl = h.board.controls
                c = ctl.get("k", "keys", 1, ("move", "pick"))
                ctl.feed(c, "pick")
                ctl.command("time 6:30")
                h.frame(0.2)
                ring = g.ring(g.wall.ms())
                check("%s clock: pick hides the seconds" % board, not g.seconds and ring[0] == ring[59] and
                      ring[0][0] == ring[0][2] and not lit(C.SECOND), ring[:2])
                check("%s clock: set by a command" % board, g.wall.hms() == (6, 30, 0))
                minute = lit(C.MINUTE)
                check("%s clock: the minute hand at 6" % board, sorted(minute) == ["E", "F", "G"] and minute["F"] == ["F3"], minute)
            finally:
                use_board(old)
    finally:
        config.RTC = config_rtc


def cards():
    """Every game's card in the game picker loads and draws something, and a folder game's card (its card.py)
    doesn't load the game: the picker loads cards while another game is running, so they have to be small."""
    h = host.Host(host.load_game("paint"), host.Board(leds.Lights(), Controls(hardware=False)), name="paint")
    lob = h.lobby
    for name in host.game_names():
        if name != "paint":
            host.unload_game(name)
        fn = lob.card_of(name)
        check("cards: %s has one" % name, fn is not None)
        if fn is None:
            continue
        if not hasattr(sys.modules["games." + name], "Game"):
            check("cards: %s's card loads without its game" % name, "games.%s.game" % name not in sys.modules,
                  [k for k in sys.modules if k.startswith("games." + name)])
        h.board.lights.raw[:] = bytes(len(h.board.lights.raw))
        fn(h.board.lights, 0.0)
        check("cards: %s's card draws" % name, any(h.board.lights.raw))
        lob.close_games()


if __name__ == "__main__":
    lights_map()
    driver()
    effects()
    roller()
    geometry()
    names()
    small_board()
    controllers()
    held_buttons()
    plug_ins()
    hosting()
    carried_bars()
    forest_fire()
    fireflies()
    aurora()
    rain()
    test_pattern()
    wall_time()
    console()
    clock()
    cards()
    print("%d failed" % len(FAILS) if FAILS else "all passed")

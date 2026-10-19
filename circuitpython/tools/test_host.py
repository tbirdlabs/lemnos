# Desktop test of the board's own parts (gamehost/), with no game's rules involved: the LED maps and placement,
# drivers, effects, the die roller, the board's geometry, controllers coming and going, plug-ins, and the host
# running the example game (games/paint.py) and the test pattern (games/testpattern.py) on a fake clock.
#   py -3 tools/test_host.py          (Salient on the board: tools/test_salient.py)

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import config
from gamehost import dice, fx, host, plugins
from gamehost import geometry as G
from gamehost import lights as leds
from gamehost.controls import ADDED, REMOVED, Controls
from gamehost.game import Game as BaseGame

FAILS = []


def check(name, ok, detail=""):
    if not ok:
        FAILS.append(name)
        print("FAIL", name, detail)


def strip(board):
    """The island's strip as built, LED by LED from the input, by name: ("line", "A1") or ("hex", "A1", i) with i
    the LED's place in the hex left to right as seen from seat 1. Row A runs left to right from the input, the end
    of each row loops to the same end of the next (line A5 to line B6 on the small board), so B, D and F run right
    to left."""
    out = []
    for r, n in enumerate((4, 5, 6, 7, 6, 5, 4)):
        row = "ABCDEFG"[r]
        run = []
        for k in range(1, n + 1):
            if board == "small":
                run.append(("line", row + str(k)))
            run += [("hex", row + str(k), i) for i in range(3)]
        if board == "small":
            run.append(("line", row + str(n + 1)))
        if r % 2:
            run.reverse()
        out += run
    return out


def lights_map():
    """Both boards: every island LED where the strip puts it, by name; the bars on their channels."""
    nb = leds.SPOTS * 3                                   # first logical bar LED
    fl = nb + 60                                          # first logical line LED
    for board, size, nlines in (("large", 111, 0), ("small", 155, 44)):
        isl, nl, strand, ph = leds.layout(board)
        check("%s: %d island LEDs, %d lines" % (board, size, nlines), (isl, nl, strand) == (size, nlines, size))
        want = strip(board)
        got = [None] * size
        for x in want:
            k = G.spot(x[1]) * 3 + x[2] if x[0] == "hex" else fl + G.line(x[1])
            got[ph[k]] = x
        check("%s: every LED in strip order" % board, got == want,
              [(i, want[i], got[i]) for i in range(size) if want[i] != got[i]][:3])
        check("%s: seat 1 bar on channel 1" % board, ph[nb] == config.BARS_AT[0][0] * size)
        check("%s: seat 6 bar LED 10" % board, ph[nb + 59] == config.BARS_AT[5][0] * size + 9)

    def at(board, x):
        isl, nl, strand, ph = leds.layout(board)
        return ph[G.spot(x[1]) * 3 + x[2] if x[0] == "hex" else fl + G.line(x[1])]
    # the same, from the wiring tables in docs/wiring.md
    check("large: A1 is LEDs 0-2", [at("large", ("hex", "A1", i)) for i in range(3)] == [0, 1, 2])
    check("large: B5 follows A4, its right LED first", [at("large", ("hex", "B5", i)) for i in range(3)] == [14, 13, 12])
    check("large: G4 ends the run", at("large", ("hex", "G4", 2)) == 110)
    check("small: line A1 is LED 0, then A1", at("small", ("line", "A1")) == 0 and
          [at("small", ("hex", "A1", i)) for i in range(3)] == [1, 2, 3] and at("small", ("line", "A2")) == 4)
    check("small: line A5 (16) loops to line B6 (17), then B5", at("small", ("line", "A5")) == 16 and
          at("small", ("line", "B6")) == 17 and [at("small", ("hex", "B5", i)) for i in range(3)] == [20, 19, 18])
    check("small: row D is 63-91, from line D8 to line D1", at("small", ("line", "D8")) == 63 and at("small", ("line", "D1")) == 91)
    check("small: G4 and line G5 end the run", at("small", ("hex", "G4", 2)) == 153 and at("small", ("line", "G5")) == 154)
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
    lt.spot(G.spot_at(3, -2), [(1, 2, 3), (4, 5, 6), (7, 8, 9)])        # B5: row B runs left
    lt.bar(2, [(10, 0, 0)] + [(0, 0, 0)] * 9)
    lt.show()
    b5 = 18 if leds.LINES else 12                         # B5's first LED on the strip: its right one
    check("driver: B5's left light is its last LED", fp.px[b5 + 2] == (1, 2, 3) and fp.px[b5] == (7, 8, 9), fp.px[b5:b5 + 3])
    check("driver: seat 2's LED 1 on channel 2", fp.px[config.BARS_AT[1][0] * leds.STRAND] == (10, 0, 0))
    lt.show()
    check("driver: an unchanged frame isn't sent again", fp.shows == 2, fp.shows)
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
    """On the small board, names land on the right LEDs: row B runs right to left from LED 17 (line B6) to 37."""
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
        check("small: line B1 (row B's left end) is LED 37", fp.px[37] == red)
        check("small: between B3 and B4 is LED 25", fp.px[25] == green)
        check("small: hex B3 is LEDs 28, 27, 26, left to right", fp.px[26:29] == [(3, 3, 3), (2, 2, 2), (1, 1, 1)], fp.px[24:30])
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


def test_pattern():
    """games/testpattern.py on both boards, through the host to a pixel object: red lights the LEDs one at a time,
    in place order (rows A-G left to right as seen from seat 1, then bars 1-6 LED 1-10), each on the strip address
    the wiring tables give; then green over it, then blue; pause, step, start over."""
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


if __name__ == "__main__":
    lights_map()
    driver()
    effects()
    roller()
    geometry()
    names()
    small_board()
    controllers()
    plug_ins()
    hosting()
    test_pattern()
    print("%d failed" % len(FAILS) if FAILS else "all passed")

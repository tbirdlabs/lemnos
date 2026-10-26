# Making a game for the board

The board is a hex island of 37 spots with 3 lights each, six seats around it with a 10-light bar each, and any mix
of controllers: big buttons, a single switch, an encoder, a gamepad, a switch box. A game for it is a Python file
(or a folder) in `circuitpython/games/`. The game never touches pins, strips or devices. It gets actions from
controllers and draws with lights, and the board takes care of the rest. So the same game runs with whatever
controllers the players need, and on boards wired differently.

Start by reading [`games/paint.py`](../circuitpython/games/paint.py), the smallest whole game (about 80 lines), and
[`gamehost/game.py`](../circuitpython/gamehost/game.py), the interface. This page is the longer version.

## The shape of a game

```python
# games/hello.py
from gamehost import geometry as G
from gamehost.game import Game as BaseGame


class Game(BaseGame):
    def __init__(self, board):
        BaseGame.__init__(self, board)
        self.lit = G.spot("D4")                     # the center hex

    def event(self, controller, action, now):
        if action == "move":
            self.lit = (self.lit + 1) % G.SPOTS     # the next hex in reading order (D5)

    def draw(self, lights, now):
        lights.spot(self.lit, [(255, 255, 255)] * 3)
```

Put `GAME = "hello"` in `config.py` and it runs at power-up. A bigger game can be a folder, `games/NAME/`, with its
`Game` class in `game.py` and anything else it needs beside it (Island Rush is `games/rush/`).

Every frame (40 a second) the host (while the game is being played; between games the lobby has the controllers
and the lights, see [A setup](#a-setup-on-the-board-and-the-usb-page-optional)):

1. tells the game about controllers that arrived or left: `controller_added(controller, now)`,
   `controller_removed(controller, now)`
2. hands it every action since the last frame, in order: `event(controller, action, now)`
3. passes on command lines typed on the serial console (or the USB page's console): `command(text, now)`, which
   returns the reply to print (or `None` for "no such command"). List them in the class attribute `HELP`, as
   (command, what it does) pairs, and the console's `help` shows them with the board's own:

   ```python
   class Game(Base):
       HELP = (("speed 3", "how fast the lights run, 1-5"),
               ("reset", "start over"))
   ```

   The board answers `help` and `mem` (free RAM) itself, and hubs add theirs (`radio`, `radio pair`), so don't
   use those words. A command starting with a console key letter (m, n, p, b, w, a, s, d) is typed with a `/` in
   front in a terminal; `help` shows it that way by itself, so write it in `HELP` without the `/`.
4. lets it run its clock: `update(now)`
5. sets every light dark, calls `draw(lights, now)`, and shows the result

A game doesn't only start at power-up: the radio's web page can switch the board to another game while it runs.
The host then makes the new game and calls `controller_added` for every controller already connected, so set
everything up in `__init__` and take players from `controller_added`, the same either way.

All six methods have do-nothing defaults; write only the ones you need. `now` is the board's clock in seconds. Use
it for all timing instead of reading the time yourself, so tests can run your game on a fake clock.

Some ground rules that keep games working on the real board:

- **`update` must be quick.** It runs between frames. A computer player that thinks for a long time should spread the
  work over several frames, or the lights stutter.
- **`draw` only draws.** Don't change the game there; the host may skip or repeat a draw.
- **Draw everything, every frame.** The lights start each frame dark. You don't need to remember what you lit last
  time.
- **Keep the rules apart from the board.** Island Rush's rules (`engine.py`) and computer player (`ai.py`) use only
  the board's shape (`gamehost/geometry.py`), never lights or controllers, so they also run in desktop tests and its
  simulator (`tools/sim_rush.py`). `game.py` is the only part that knows about
  lights and controllers. It's worth doing the same.

## The board: `gamehost/geometry.py`

Everything has a name, as seen from seat 1 (Player One, at the bottom):

- **Rows** A to G, from the farthest from seat 1 (A) to the nearest (G): 4, 5, 6, 7, 6, 5 and 4 hexes.
- **Hexes** ("spots"): the row and 1 to n, left to right. A1–A4, B1–B5, C1–C6, D1–D7 (D4 is the center), E1–E6,
  F1–F5, G1–G4.
- **Lines:** the vertical edges in a row. The small board has an LED under each; the large board has none. A row has
  one more line than hexes, also counted from 1, left to right: line B1 is row B's left end, line Bk is just left of
  hex Bk, and line B6 is the right end. So hex Bk sits between lines Bk and Bk+1. The slanted edges between rows
  have no LEDs.

Inside, hexes and lines are also numbered, in reading order (row A first, each left to right): hexes 0-36, lines
0-43. The numbers are handy for arrays and loops (`for t in range(G.SPOTS)`), and they have nothing to do with how
the LED strip runs. Anything that takes a hex or a line takes its name or its number, except the `View` cursor
methods below, which use numbers.

| | What it is |
| --- | --- |
| `spot("B3")`, `name(t)` | A hex's number from its name, and back |
| `line("B4")`, `line_name(k)` | A line's number from its name, and back |
| `left_line(t)`, `right_line(t)` | The lines either side of a hex: lines B3 and B4 for hex B3 |
| `between(a, b)` | The line between two hexes side by side in a row: `between("B3", "B4")` is line B4 |
| `line_spots(k)` | The hexes beside a line: two, or one at a row's end |
| `neighbors(t)`, `adjacent(a, b)` | The 3-6 hexes touching t (as numbers); whether two hexes touch |
| `SPOTS`, `LINES`, `SEATS`, `BAR_LEDS` | 37, 44, 6, 10 |
| `ROWS[r]`, `ROW[t]`, `COL[t]` | The hexes of each row (r = 0 for A to 6 for G); hex t's row and place in it (from 0) |
| `Q[t]`, `R[t]`, `spot_at(q, r)`, `DIRECTIONS` | Axial hex coordinates (D4 at (0, 0), R = -3 at row A), back to a hex (-1 off the island), the 6 steps |
| `SIDES[seat]` | The 4 coast hexes facing a seat, left to right as that player sees them |
| `VIEWS[seat]` | That seat's view of the island (below) |

Seats are numbered 1-6 clockwise from seat 1 at the bottom (row G's side). Every player looks at the island from their
own side, so "left", "up" and "the next spot" mean different things at different seats. A `View` handles that:

| `VIEWS[seat].` | What it is |
| --- | --- |
| `rows[r]` | The rows as that player sees them: 0 = farthest, 6 = nearest, each left to right |
| `row[t]`, `x[t]` | Spot t's row in that view, and its left-to-right position |
| `reading`, `order[t]` | All 37 spots in reading order (far row first, left to right); spot t's place in it |
| `arrow(pos, key)` | Where `"up"`, `"down"`, `"left"` or `"right"` takes a cursor at pos. Down from the nearest row is the player's bar, `ON_BAR` |
| `path(frm, to)` | The cursor positions passed going from frm to to by arrows. A computer player can walk its cursor along it so people can follow what it does |

## Drawing: `board.lights`

```python
lights.spot("B3", [c0, c1, c2])         # a hex's 3 lights, left to right as seen from seat 1
lights.line("B4", color)                # a line's LED (small board; nothing on the large board)
lights.between("B3", "B4", color)       # the line between two hexes side by side (here line B4)
lights.bar(seat, [c0, ... c9])          # a seat's 10-light bar; c0 is LED 1, at that player's left
lights.bar_at(n, [c0, ... c9])          # bar n by place (BARS_AT), whoever sits there: for a picture round the board
lights.has_lines                        # True on the small board
```

A bar can be built into a controller and go with it ([controllers.md](controllers.md)): `lights.bar(seat, …)` then
lands on whichever bar that seat's player holds, so draw players' bars by seat and the board does the rest.

Hexes and lines can be given by number too (`lights.spot(t, …)` in a loop). The same game runs on both boards: on
the large one, drawing a line does nothing. If a game shows something important with lines, check
`lights.has_lines` and show it another way on the large board.

Colors are `(r, g, b)`, each 0-255; lower is dimmer. The board caps the total current, dimming the whole frame if it
has to, so don't worry about lighting everything.

A spot's 3 lights read differently from different seats: the left light for seat 1 is the right one for seat 4.
Symmetric patterns read the same from everywhere. Island Rush shows 1 light as the middle one, 2 as the outer two and
3 as all three.

**Effects** ([`gamehost/fx.py`](../circuitpython/gamehost/fx.py)): pass one after the colors, for the whole group or as
a list with one per light.

```python
from gamehost import fx
lights.spot(t, colors, fx.breathe(3))           # a 3-second breath
lights.bar(seat, colors, fx.blink(fx.FAST))     # named speeds: fx.SLOW 3 s, fx.NORMAL 1.5 s, fx.FAST 0.6 s
lights.spot(t, colors, [None, fx.flash(0.5), None])
```

| Effect | Does |
| --- | --- |
| `fx.STEADY` (or no effect) | Just the color |
| `fx.blink(period, duty=0.5)` | On for `duty` of each cycle, off for the rest |
| `fx.breathe(period, low=0.3)` | Smooth fade down to `low` of full and back, never dark |
| `fx.flash(period, other=white, duty=0.4)` | Swaps between the color and `other` |
| `fx.chase(period, tail=0, reverse=False)` | One light running along the group (a bar's LED 1 to 10) once a cycle |

To make your own, subclass `fx.Effect` and write `at(color, phase, i, n)`: phase runs 0 to 1 through the cycle, and
i of n is the light's place in its group. Every effect runs off the board's one clock, so everything with the same
effect and speed stays in step. Make effects once (at the top of your file) and reuse them.

Two board-wide rules apply to every effect, whatever a game asks for. Nothing that switches lights on and off
(`on_off = True`, like blink and flash) runs faster than 3 times a second, because faster flashing can set off
photosensitive seizures. And `EFFECT_TIME_SCALE` in `config.py` slows every effect for players who need more time.

**Dice** ([`gamehost/dice.py`](../circuitpython/gamehost/dice.py)): a light runs along a bar and slows to stop on the
result. The game decides the result; the roller only animates it.

```python
from gamehost import dice
roll = dice.Roll(now, result)           # result 1-10
roll.duration                           # seconds until it has landed and held: schedule what comes next
roll.draw(lights, seat, background)     # each frame, over the bar's 10 colors
dice.d(6)                               # a random 1-6, if the game doesn't keep its own random numbers
dice.seed()                             # a random 32-bit number to seed a game's own generator
```

Seed your own generator from `dice.seed()` and keep the seed, and a game can be replayed exactly. Island Rush does this.

## The time of day: `gamehost/walltime.py`

For a game that needs the real time (the clock, `games/clock.py`): `w = walltime.Wall()` once, `w.update()` every
frame, then `w.ms()` (milliseconds since midnight), `w.hms()`, and `w.known` (False until the time's been set). It
reads an RTC chip on the I2C bus if `config.RTC` names one, and otherwise keeps time on the board while it's on.
Pass console commands to `w.command(text)` from your game's `command()` and players can set it by typing
`time 14:32` (list it in `HELP`, as `games/clock.py` does); `tools/settime.ps1 COM16` sends the computer's time,
and so does the USB page when it connects.

## Controllers and actions

Every input device is turned into the same few actions
([`gamehost/actions.py`](../circuitpython/gamehost/actions.py)):

| Action | Typically |
| --- | --- |
| `"move"` | Step forward through what can be picked: a button, an encoder turned clockwise, a scan tick on one switch |
| `"move_back"` | Step backward: an encoder turned the other way |
| `"pick"` | Choose what the cursor is on |
| `"back"` | Go back, cancel |
| `"up"`, `"down"`, `"left"`, `"right"` | A D-pad or joystick |

A `controller` in `event()` is the same object every time for the same device, so it can be a dictionary key. It has:

| | |
| --- | --- |
| `controller.seat` | The seat it's at (1-6), or `None`: let its player choose one, or put it somewhere sensible |
| `controller.can` | The set of actions it can send. It can change while connected (an I2C pad can say it's a single switch) |
| `controller.name`, `.id` | For people, and a stable id |
| `controller.connected` | `False` between `controller_removed` and the next `controller_added` |

`board.controllers` lists the ones connected now.

**Design for one switch.** The least a controller can send is `move` (the board scans for the player, stepping at a
steady pace) and `pick`. If your game needs `back`, check `"back" in controller.can`, and when it isn't there, add a
stop the player can pick instead. The board's lobby puts a way-back stop in each setup field. Arrows are
nice to have, never required.

**Controllers come and go.** Wired ones arrive at power-up. Gamepads on I2C boards and the serial console arrive the
first time they're used, and gamepads can disconnect. Decide what your game does then: hand the player to the
computer, pause, or ignore it.

## A setup, on the board and the USB page (optional)

A game with no setup (paint, the clock) just runs from the moment it's made (menu still leaves it). A game that needs one (who plays,
which side, how many, how hard) doesn't build its own setup screens. It lists its setup as fields, and the board's
**lobby** (`gamehost/lobby.py`) walks people through them, the same way for every game:

- **Joining:** anyone presses pick to join. Each player sets their own fields (a seat, a color, a side) on their
  own bar: move steps through the choices, pick takes one, back goes back a field, and back on the first field
  leaves. The first to join leads: after their own fields they set the game's other fields, then their bar
  breathes green and pick starts the game. With nobody joined, back opens the **game picker**: the island shows
  each game's card, move steps, pick plays that game.
- **During the game** your game has the controllers, as before.
- **When it's over** (your `finished()` says so) the lobby takes over again: pick plays again with the same choices,
  back returns to the setup with everyone still in it, so anyone can change their seat or color before the next one.
- A controller without back (one switch) gets a way-back stop after the last choice of every list, its bar dim red.
- **Menu**, from any game at any time, even one with no setup: a wired switch held 3 s, the console's `q`, the USB
  page's Menu. The board pauses your game (no `update`) and asks on the player's bar, green with one red light; only
  picking the red light opens the game picker, and anything else returns to your game as it was. Your game never sees
  the menu action, so it needs nothing for it.

The USB page shows the same fields as a form with a **Start** button, and its **New game at the board** makes your
`Game` afresh, back at its setup on the board. Four methods:

```python
    def options(self, choices=None):
        """The fields. choices: what's chosen so far on the board (None from the page)."""
        out = [{"key": "speed", "label": "Speed", "value": "1", "bar": "fill",
                "choices": [("1", "Slow"), ("2", "Medium"), ("3", "Fast")]}]
        for c in self.board.controllers:              # each controller's own fields
            out.append({"key": "seat:" + c.id, "label": c.name, "player": c.id, "out": "out",
                        "unique": "seat", "seat": True, "value": str(c.seat or 1),
                        "choices": [("out", "Sits out")] + [(str(x), "Seat %d" % x) for x in range(1, 7)]})
        return out

    def setup(self, choices, now):
        """choices: {"speed": "2", "seat:wired0": "4", ...}, strings."""
        ...                                           # start the game
        return None                                   # it started (or a message saying why not: nothing started)

    def preview(self, lights, now, lobby):
        """Draw the setup as chosen so far: lobby.choices, lobby.joined, lobby.editing(controller)."""

    def finished(self):
        """True once the game is over and its last picture is up."""
        return self.over
```

Each field is a list of choices: `(value, label)` with string values, or `(value, label, color)` to show the choice
in that color on the bar. `value` is the one chosen to begin with. For the board:

| Key | What it does |
| --- | --- |
| `player` | a controller's id: this is that player's own field, set on their own bar after they join. Give every connected controller its own copy, keyed by its id |
| `out` | (a player's field) the value for "not playing"; players who haven't joined have it |
| `unique` | (a player's field) a name: no two players have the same value in fields with that name (seats, colors) |
| `seat` | (a player's field) `True`: the value is the seat where that player's bar is |
| `bar` | `"fill"`: the bar lights as many as the value (how many, a level), not a light per choice |
| `color` | the bar's color for a `"fill"` field |
| `board` | `False`: not shown on the board; the value is whatever `options()` works out from the other choices |

and for the page, `show` (`{key: [values]}`: show the field only while those fields have one of those values) and
`note` (a line under it). The lobby calls `options(choices)` again whenever something changes, so the form can follow
what's chosen: fewer players to choose from once more have joined, a difficulty only when one person plays the
computer. `setup()` gets every field's value, also from the page, so check them: a controller can leave in between.
Island Rush (`games/rush/game.py`) is a full example.

**A card for the game picker:** a picture of your game, drawn while people choose. In a one-file game, a
module-level `card(lights, now)`; in a folder, `card.py` with `draw(lights, now)`, so the picker can show it without
loading the whole game. Without one, the picker shows a plain card.

## Trying a game

On the desktop, from `circuitpython/`, the host runs with no hardware: no LEDs, and controllers only send what you
feed them. Drive it with a fake clock:

```python
from gamehost import host
from gamehost.controls import Controls
from gamehost.lights import Lights

h = host.Host(host.load_game("hello"), host.Board(Lights(), Controls(hardware=False)))
pad = h.board.controls.get("t1", "test pad", 1, ("move", "pick"))
h.board.controls.feed(pad, "move")
h.frame(0.0)                             # one frame at t = 0 s; look at h.game, or h.board.lights.sent
```

`tools/test_host.py` tests the example game this way, and `tools/test_rush.py` plays whole Island Rush games through
the board's controls.

On the board, set `GAME` in `config.py`. The USB serial console works as up to 6 controllers: type m (move), n (move
back), p (pick), b (back), w/a/s/d (arrows), q (menu: back to the game picker), and a digit 1-6 to switch
controllers. A line that starts with any other letter (or with `/`) is a command for the game, sent with Enter:
`time 14:32` for the clock.

## Changing the hardware instead

None of this needs a game to change:

- **Different controllers:** list them in `config.py` (types in [controllers.md](controllers.md)). A new kind of
  input is a small class with `can` and `poll(now, emit)`. Put it in its own file and name it in `config.py` as
  `"file.Class"`.
- **Different wiring or LED driver:** `LED_DRIVER`, `LED_PIN`, `ISLAND_START`, `ISLAND_AT` and `BARS_AT` in `config.py` ([wiring.md](wiring.md)).
  A plain NeoPixel strand on any CircuitPython board works with `LED_DRIVER = "neopixel"`, and other LED hardware
  takes a driver function (`gamehost/drivers.py`).
- **A new source of many controllers** (Bluetooth straight to the board, a network): a hub (`gamehost/hubs.py`),
  named in `CONTROLLER_HUBS`.

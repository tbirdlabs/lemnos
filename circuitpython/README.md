# Salient on CircuitPython (Feather RP2040 SCORPIO)

The board's software. It's split so other games can be swapped onto the board: the host, the lights and the
controllers know nothing about Salient, and Salient knows nothing about pins or devices.

| File | What it is |
| --- | --- |
| `config.py` | **Edit this one.** LED channels, power limit, controllers (wired inputs, I2C boards, serial console), which game runs. |
| `host.py`, `code.py` | The host: polls the controllers, runs the game, draws the frame. `code.py` starts it at power-up. |
| `fx.py` | Light effects for any game: blink, breathe, flash, chase, with speeds; add your own. |
| `dice.py` | The die roller for any game: a light runs along a bar and slows to stop on the result. |
| `leds.py` | The lights: 37 spots × 3 LEDs, six 10-light bars and (144 LEDs/m map) the line LEDs, mapped to the wiring in `docs/wiring.md`, with the power cap. `config.LED_MAP` picks `60_leds_per_meter` or `144_leds_per_meter`. |
| `controls.py` | The controllers: buttons, encoders, one-switch scan, resistor ladders, I2C controller boards (`docs/controllers.md`) and the serial console, all turned into actions. |
| `salient_game.py` | Salient as a game: setup, the play UI (cursor, row-then-spot scan, chance and roll on the bar, keep going), watching the computer. Ported from `ui.js`. |
| `engine.py` | Rules engine, a line-for-line port of `engine.js`. No hardware. Integers only. |
| `ai.py` | The computer player, a line-for-line port of `ai.js` (integer-only, so it matches exactly). |
| `difficulty.py` | Difficulty levels 1–10, a port of `difficulty.js`. |
| `rules.py` | Default settings, generated from `settings.js` by `gen_rules.js`; don't edit by hand. |
| `bench.py` | Bring-up: times every AI move and reports free RAM, drawing each position on the LEDs. |
| `test_board.py` | Desktop test: plays whole games through the board UI with simulated controllers. |
| `replay_py.py`, `replay_js.js`, `profile_worst.py` | Desktop only: the JS / Python comparison and the profiler. |

## A game on the board

A game is a module with a `Game` class; `config.GAME` names the one that runs.

```python
class Game:
    def __init__(self, board): ...          # board.lights, board.controls, board.seats (6)
    def event(self, controller, action, now): ...   # one action from one controller
    def update(self, now): ...              # every frame: timers, animations, computer players
    def draw(self, lights, now): ...        # draw the frame; the host clears it first and shows it after
```

- **Lights:** `lights.spot(t, [c0, c1, c2])` (spot t in the engine's numbering, light 0 = left as seen from seat 1),
  `lights.bar(seat, [10 colors])` (seat 1–6, light 0 = LED 1 at the player's left), `lights.line(row, k, color)`
  (144 LEDs/m map only: the line LED k in row 0–6, 0 = the row's left end as seen from seat 1). Colors are (r, g, b),
  each 0–255; lower values are dimmer.
- **Effects** (`fx.py`): pass one after the colors, for the whole group or as a list with one per LED.

  ```python
  lights.spot(t, colors, fx.breathe(3))          # a 3-second breath
  lights.bar(seat, colors, fx.blink(fx.FAST))    # named speeds: fx.SLOW 3 s, fx.NORMAL 1.5 s, fx.FAST 0.6 s
  lights.spot(t, colors, [None, fx.flash(0.5), None])
  ```

  | Effect | Does |
  | --- | --- |
  | `fx.STEADY` (or no effect) | Just the color |
  | `fx.blink(period, duty=0.5)` | On for `duty` of each cycle, off for the rest |
  | `fx.breathe(period, low=0.3)` | Smooth fade down to `low` of full and back, never dark |
  | `fx.flash(period, other=white, duty=0.4)` | Swaps between the color and `other` |
  | `fx.chase(period, tail=0, reverse=False)` | One light running along the group (a bar's LED 1 to 10) once a cycle |

  These are examples. To make your own, subclass `fx.Effect` and write `at(color, phase, i, n)`: phase runs 0 to 1
  through the cycle, and i of n is the LED's place in its group. Every effect runs off the board's one clock, so
  everything with the same effect and speed stays in step. `EFFECT_TIME_SCALE` in `config.py` slows every effect at
  once (1.5 = 1.5x slower). Nothing that switches lights on and off (an effect with `on_off = True`, like blink and
  flash) runs faster than 3 times a second, whatever a game asks for: faster flashing can set off photosensitive
  seizures.
- **Die roller** (`dice.py`): shows a roll on a seat's bar. The game decides the result (its own seeded random
  numbers, or `dice.d(n)`); the roller only animates it.

  ```python
  roll = dice.Roll(now, result)                 # result 1-10; runs LED 1-10 once, then slows to stop on the result
  roll.duration                                 # seconds until it has landed and held: schedule what comes next
  roll.draw(lights, seat, background)           # each frame: the running light over the bar's 10 colors
  ```

  `Roll(now, result, n=10, laps=1, color=white)`; `roll.done(now)`, `roll.position(now)`. Timing follows
  `EFFECT_TIME_SCALE`.
- **Actions:** `move`, `move_back`, `pick`, `back`, `up`, `down`, `left`, `right`.
- **Controllers:** `controller.seat` (1–6, or None if its player chooses a side), `controller.can` (the actions it
  can send; a game should offer a way out when `back` isn't there), `controller.name`.

Nothing in `host.py`, `leds.py`, `controls.py`, `fx.py` or `dice.py` changes for a new game.

## Salient on the board

- **Setup:** move cycles the island previews (Invasion, Defender, Island Rush), pick chooses. The chooser sits at
  their controller's seat (seat 1 if it has none) and the island is laid out around them. Another controller can
  press pick to take the other side; otherwise the computer plays it, and move sets the difficulty (1–10 lights on
  the chooser's bar, 7 = fair). Pick starts. Island Rush isn't built yet (its preview blinks).
- **Each player sees the island from their own side:** rows run across their side, far to near, and their bar is
  past their nearest row. Move steps through the rows with something to pick, then the bar; pick opens a row; move
  steps through its spots; pick picks; back returns to the rows. Arrows move the cursor directly. A controller
  without back gets a way-out stop at the end of each row (the whole row lights) and, while keeping going, a stop
  on its bar.
- **Lights on a spot:** 1 light = the middle LED, 2 = the outer two, 3 = all, so it reads the same from every side.
  The cursor lights a spot's empty LEDs dim white and flashes its lit ones; cut-off spots blink; the winner pulses.
- **The computer** plays at watch speed: its cursor walks to the spot, the chance shows on its bar, the roll runs.

## Keeping the ports in step

- After changing `settings.js`: `run-node circuitpython/gen_rules.js` (or VS Code's runtime) rewrites `rules.py`.
- After changing `engine.js` or `ai.js`: make the same change in the `.py` file, then compare:
  `run-node circuitpython/replay_js.js 500 > js500.txt`, `py -3 replay_py.py 500 > py500.txt`,
  `diff --strip-trailing-cr js500.txt py500.txt` (empty = identical). `--log SEED` prints one game's moves;
  `SALIENT_FACE=0` in the environment puts the attacker on the top side.
- After changing `salient_game.py`: `py -3 test_board.py`.

## On the board

1. Install CircuitPython 9 for the Feather RP2040 SCORPIO, and from the bundle: `adafruit_neopxl8`.
2. Compile with CircuitPython's own `mpy-cross` (matching the firmware version) and copy the `.mpy` files plus
   `code.py` and `config.py` to CIRCUITPY. Compiling the source on the board itself needs a lot more RAM than
   running it.
3. Wire to `docs/wiring.md`, or change `config.py` to match your wiring.
4. Bring-up: run `bench.py` first (from the REPL: `import bench; bench.main()`). It prints the worst AI move time and
   the lowest free RAM, and draws each position, which checks the LED map.
5. Then `code.py` runs the game. The serial console works as up to 6 controllers for testing (m, n, p, b, w/a/s/d;
   a digit switches controller).

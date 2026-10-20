# The board's software (CircuitPython, Feather RP2040 SCORPIO)

The board is a game platform: a hex island of lights, six seats with a bar each, and any mix of controllers. It's
split in two so anyone can write a game for it, or build one with different parts:

- **`gamehost/`** knows the hardware (LEDs, controllers, wiring) and nothing about any game.
- **`games/`** know their rules and nothing about pins, strips or devices.

They meet in one small interface, the `Game` class in [`gamehost/game.py`](gamehost/game.py). To write a game, read
[docs/making-games.md](../docs/making-games.md); `games/paint.py` is a whole game in about 80 lines.

| Where | What it is |
| --- | --- |
| `config.py` | **Edit this one.** Which game runs, which board (large or small), the LED driver and where the LEDs are, the controllers. |
| `code.py` | Starts the host at power-up. |
| `gamehost/game.py` | The `Game` base class: the whole interface between the board and a game. |
| `gamehost/host.py` | Runs a game: tells it about controllers, hands it their actions, has it draw, shows the frame. |
| `gamehost/geometry.py` | The board's shape: hex and line names (A1–G4), neighbors, each seat's side and view, arrow-key moves. |
| `gamehost/lights.py` | Drawing by hex, line and bar, by name; the LED map of both boards (`docs/wiring.md`); the power cap. |
| `gamehost/drivers.py` | LED drivers: NeoPXL8 (8 outputs), one NeoPixel strand, or none. |
| `gamehost/fx.py`, `dice.py` | Light effects (blink, breathe, flash, chase, with the flash-rate limit); a die roll on a bar. |
| `gamehost/actions.py` | The actions controllers send: move, move back, pick, back, up, down, left, right. |
| `gamehost/controls.py` | Controllers: the inputs and hubs below, turned into (controller, action). |
| `gamehost/inputs.py` | Wired inputs: button, encoder, one-switch scan, resistor ladder (`docs/controllers.md`). |
| `gamehost/hubs.py` | Sources with their own controllers: I2C controller boards, the serial console (which also takes typed commands for the game). |
| `gamehost/walltime.py` | The time of day: an RTC chip on the I2C bus (`config.RTC`) or the board's own clock; `time 14:32` on the console sets it. |
| `gamehost/plugins.py` | How `config.py` names your own drivers, inputs, hubs and games (`"module.Name"`). |
| `games/paint.py` | The example game: paint spots in your color. Also a quick test of every light and controller. |
| `games/testpattern.py` | Test pattern: red, then green, then blue fill every LED one at a time, left to right; pause and step to print an LED's strip address. |
| `games/clock.py` | An analog wall clock: the island is the face, the six bars a 60-light minute ring. |
| `games/salient/` | Salient: `game.py` (the board's side: setup, play UI, the computer's turns), `engine.py` (rules), `ai.py`, `difficulty.py`, `rules.py` (generated; don't edit), `bench.py` (bring-up). |
| `tools/` | Desktop only, never copied to the board: tests, the JS / Python replay comparison, the profiler, `gen_rules.js`, `settime.ps1` (sets the board's clock from this computer). |

## Tests (desktop, from this folder)

```
py -3 tools/test_host.py        the board's parts: LED maps, drivers, effects, dice, geometry, controllers, host, paint, test pattern, clock
py -3 tools/test_salient.py     Salient played through the board UI by simulated controllers, checked against the engine
```

## Salient on the board

- **Setup:** move cycles the island previews (Invasion, Defender, Island Rush), pick chooses. The chooser sits at
  their controller's seat (seat 1 if it has none) and the island is laid out around them. Another controller can
  press pick to take the other side; otherwise the computer plays it, and move sets the difficulty (1–10 lights on
  the chooser's bar, 7 = fair). Pick starts. Island Rush: each player picks a side and a color; the first sets the
  number of players and the difficulty.
- **Each player sees the island from their own side:** rows run across their side, far to near, and their bar is
  past their nearest row. Move steps through the rows with something to pick, then the bar; pick opens a row; move
  steps through its spots; pick picks; back returns to the rows. Arrows move the cursor directly. A controller
  without back gets a way-out stop at the end of each row (the whole row lights) and, while keeping going, a stop
  on its bar.
- **Lights on a spot:** 1 light = the middle LED, 2 = the outer two, 3 = all, so it reads the same from every side.
  The cursor lights a spot's empty LEDs dim white and flashes its lit ones; cut-off spots blink; the winner pulses.
- **The computer** plays at watch speed: its cursor walks to the spot, the chance shows on its bar, the roll runs.

## Keeping Salient's ports in step

`engine.py`, `ai.py`, `difficulty.py` and `rules.py` are line-for-line ports of the browser prototype's JS, so the
same seed plays the same game on both. They import nothing from `gamehost/`.

- After changing `settings.js`: `run-node circuitpython/tools/gen_rules.js` (or VS Code's runtime) rewrites
  `games/salient/rules.py`.
- After changing `engine.js` or `ai.js`: make the same change in the `.py` file, then compare:
  `run-node circuitpython/tools/replay_js.js 500 > js500.txt`, `py -3 tools/replay_py.py 500 > py500.txt`,
  `diff --strip-trailing-cr js500.txt py500.txt` (empty = identical). `--log SEED` prints one game's moves;
  `SALIENT_FACE=0` in the environment puts the attacker on the top side.
- After changing `games/salient/game.py`: `py -3 tools/test_salient.py`.

## On the board

1. Install CircuitPython 10 for the Feather RP2040 SCORPIO (tested on 10.3.1), and from the 10.x bundle into
   `lib/`: `adafruit_neopxl8`, `adafruit_pioasm` and `adafruit_pixelbuf` (or `neopixel` with
   `LED_DRIVER = "neopixel"`).
2. Compile with CircuitPython's own `mpy-cross` (matching the firmware version). Copy to CIRCUITPY: `code.py` and
   `config.py` as they are, the `gamehost/` and `games/` folders with each `.py` compiled to `.mpy` except the
   `__init__.py` files (copy those as they are). Leave out `tools/`. Compiling the source on the board itself needs
   a lot more RAM than running it.
3. Wire to `docs/wiring.md`, or change `config.py` to match your wiring.
4. Bring-up: run Salient's bench first (from the REPL: `from games.salient import bench; bench.main()`). It prints
   the worst AI move time and the lowest free RAM, and draws each position, which checks the LED map. To check
   every LED, color and address, set `GAME = "testpattern"`: red, green and blue each fill the board one LED at
   a time, rows A to G left to right as seen from seat 1, then the bars seat 1 to 6, so an LED out of turn is mapped
   wrong. Pick pauses; move steps and prints the LED's channel and address. To check every controller by hand, set
   `GAME = "paint"`.
5. Then `code.py` runs the game. The serial console works as up to 6 controllers for testing (m, n, p, b, w/a/s/d;
   a digit switches controller). A line starting with any other letter is a command for the game, such as
   `time 14:32` for the clock (`GAME = "clock"`); `powershell -File tools\settime.ps1 COM16` sends this computer's time.

# Salient on CircuitPython (Feather RP2040 SCORPIO)

A port of the JS rules engine and AI. It plays exactly the same games: 500 seeds replayed in desktop Python
match the JS engine move for move (player, verb, spot and roll on every move; 255,876 moves).

| File | What it is | Compiled (.mpy) |
| --- | --- | --- |
| `engine.py` | Rules engine, a line-for-line port of `engine.js`. No hardware. Integers only. | 7.4 KB |
| `ai.py` | The AI, a line-for-line port of `ai.js` (integer-only, so it matches exactly). | 4.0 KB |
| `rules.py` | Default settings, generated from `settings.js` by `gen_rules.js`; don't edit by hand. | 0.5 KB |
| `board_io.py` | Hardware: the LED strip and the three inputs (move / pick / back). Knows nothing about games. | 1.2 KB |
| `salient_game.py` | Salient as a game plug-in: new game, AI move, draw the state on the LEDs. | 0.8 KB |
| `bench.py`, `code.py` | Bring-up: times every AI move and reports free RAM; `code.py` runs it at power-up. | 1.1 KB |
| `replay_py.py`, `replay_js.js`, `profile_worst.py` | Desktop only: the JS / Python comparison and the profiler. | – |

## Adding a game

A game is its own module (like `salient_game.py`) with `new_game(seed, rules)`, `ai_move(st)`, `render(st, brd)`,
`over(st)` and `winner(st)`, plus whatever rules and AI modules it needs. It draws through `board_io.Board`
(`set_spot`, `set_bar`, `show`) and reads `Board.events()` ("move", "pick", "back"). Nothing in `board_io.py`
changes for a new game.

## Keeping the ports in step

- After changing `settings.js`: `run-node circuitpython/gen_rules.js` (or VS Code's runtime) rewrites `rules.py`.
- After changing `engine.js` or `ai.js`: make the same change in the `.py` file, then compare:
  `run-node circuitpython/replay_js.js 500 > js500.txt`, `py -3 replay_py.py 500 > py500.txt`,
  `diff --strip-trailing-cr js500.txt py500.txt` (empty = identical). `--log SEED` prints one game's moves.

## On the board

1. Install CircuitPython 9 for the Feather RP2040 SCORPIO, and the `neopixel` library from the bundle.
2. Compile with CircuitPython's own `mpy-cross` (matching the firmware version) and copy the `.mpy` files plus
   `code.py` to CIRCUITPY. Compiling 17 KB of source on the board itself needs a lot more RAM than running it.
3. Set the placeholder pins at the top of `board_io.py`.
4. Watch the serial console: `bench.py` prints the worst AI move time and the lowest free RAM.

Not ported yet: the play UI (cursor, row-then-spot scan, chance and roll on the bar, setup and difficulty);
it lives in `ui.js` today.

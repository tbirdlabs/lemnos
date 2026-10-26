# Lemnos board software (CircuitPython, Feather RP2040 SCORPIO)

Lemnos is a game platform: a hex island of lights, six seats with a bar each, and any mix of controllers. It's
split in two so anyone can write a game for it, or build one with different parts:

- **`gamehost/`** knows the hardware (LEDs, controllers, wiring) and nothing about any game.
- **`games/`** know their rules and nothing about pins, strips or devices.

They meet in one small interface, the `Game` class in [`gamehost/game.py`](gamehost/game.py). To write a game, read
[docs/making-games.md](../docs/making-games.md); `games/paint.py` is a whole game in about 80 lines.

| Where | What it is |
| --- | --- |
| `Lemnos.html` | **The USB page.** Open it from the CIRCUITPY drive in Edge, Chrome or Firefox: the board's lights on screen, the game, brightness, the clock, the players, an on-screen controller and the console. Nothing to install. |
| `config.py` | **Edit this one.** Which game runs, which board (large or small), the LED driver and where the LEDs are, the controllers. |
| `code.py` | Starts the host at power-up. |
| `gamehost/game.py` | The `Game` base class: the whole interface between the board and a game. |
| `gamehost/host.py` | Runs a game: tells it about controllers, hands it their actions, has it draw, shows the frame. |
| `gamehost/lobby.py` | Between games, the same for every game: the game picker (each game's card), joining, the game's setup fields (its `options()`), play again or back to the setup when it ends. |
| `gamehost/geometry.py` | The board's shape: hex and line names (A1–G4), neighbors, each seat's side and view, arrow-key moves. |
| `gamehost/lights.py` | Drawing by hex, line and bar, by name; the LED map of both boards (`docs/wiring.md`); the power cap. |
| `gamehost/drivers.py` | LED drivers: NeoPXL8 (8 outputs), one NeoPixel strand, or none. |
| `gamehost/fx.py`, `dice.py` | Light effects (blink, breathe, flash, chase, with the flash-rate limit); a die roll on a bar. |
| `gamehost/actions.py` | The actions controllers send: move, move back, pick, back, up, down, left, right. |
| `gamehost/controls.py` | Controllers: the inputs and hubs below, turned into (controller, action). |
| `gamehost/inputs.py` | Wired inputs: button, encoder, one-switch scan, resistor ladder (`docs/controllers.md`). |
| `gamehost/ctltest.py` | Wired controller test, without the host: each controller's encoder adds and takes lights off its seat's bar, pick and back step its color, and the console prints every pin change and encoder count. From the REPL: `from gamehost import ctltest; ctltest.main()`. |
| `gamehost/hubs.py` | Sources with their own controllers: I2C controller boards, the serial console (which also takes typed commands for the game). |
| `gamehost/link.py` | The text protocol the radio and the USB page share (IN, CTL, TIME, SET, HELLO lines). |
| `gamehost/usbpage.py` | The USB page's side on the board: answers it over the serial console, sends it the lights and what changed. |
| `gamehost/saved.py` | Settings remembered through power-off (the game, brightness), set from the USB page or the radio's web page; `config.py` is the default. |
| `gamehost/radio.py` | The radio co-processor on TX/RX (`radio/`): Bluetooth and phone controllers by player slot, settings from its web page (brightness, the game), the time. |
| `gamehost/walltime.py` | The time of day: from the radio if there is one, else an RTC chip on the I2C bus (`config.RTC`) or the board's own clock; `time 14:32` on the console sets it. |
| `gamehost/plugins.py` | How `config.py` names your own drivers, inputs, hubs and games (`"module.Name"`). |
| `games/paint.py` | The example game: paint spots in your color. Also a quick test of every light and controller. |
| `games/testpattern.py` | Test pattern: red, then green, then blue fill every LED one at a time, left to right; pause and step to print an LED's strip address. |
| `games/clock/` | An analog wall clock: the island is the face, the six bars a 60-light minute ring. |
| `games/fire/` | Forest fire, an attract screen or wall decoration: the forest grows back and lightning burns it, small fires and now and then a big one; pick calls down lightning. `sim()` in its `game.py` runs its rules on a computer to tune them. |
| `games/fireflies/` | Fireflies, another attract screen: an evening of fireflies at single LEDs. One alone, then another answers, then more until all are out; they slowly fall into step and glow together, then go out one by one and the next evening starts. Pick starts the evening over. `sim()` in its `game.py` tunes it. |
| `games/aurora/` | Aurora, another attract screen: curtains of northern lights, green at the edge to violet above, building to a display and fading, now and then a surge with a pink fringe. Pick sets off a surge. |
| `games/rain/` | Rain, another attract screen: showers on a pond, each drop a ring spreading across every LED, from a few first drops to a downpour and back to still. Pick drops a pebble. |
| `games/rush/` | Island Rush, the board's first game (`config.GAME`): `game.py` (setup fields, play UI, the tigers on the lights), `engine.py` (rules), `ai.py` (the computer players), `card.py`. |
| `tools/` | Desktop only, never copied to the board: tests, the Island Rush simulator (`sim_rush.py`), `deploy.ps1` (puts the software on the board), `settime.ps1` (sets the board's clock from this computer). |

## Tests (desktop, from this folder)

```
py -3 tools/test_host.py        the board's parts: LED maps, drivers, effects, dice, geometry, controllers, host, paint, test pattern, clock
py -3 tools/test_rush.py        Island Rush: its rules, and whole games through the board UI by simulated controllers
py -3 tools/test_radio.py       the radio hub over a fake UART, and a two-player Island Rush played through it
py -3 tools/test_usbpage.py     the USB page's side: its lines, players, settings saved and restored, the lights sent
run-node tools/test_page.js     Lemnos.html itself, without a browser, against the board software on this computer
                                (tools/page_bridge.py); no Node: set ELECTRON_RUN_AS_NODE=1 and run it with VS Code's Code.exe
```

## Playing on the board

- **Setup** (the board's lobby, the same for every game: `gamehost/lobby.py`, with each game's own fields): press
  pick to join, move steps through a field's choices, pick takes one. In Island Rush that's a corner (your seat),
  then a color; the first to join then sets how many play, and the computer plays every seat no one takes. Then
  their bar breathes green: pick starts. A controller without back gets a way-back stop in each field. After a game,
  pick plays again; back returns to the setup (everyone still in it), and back with nobody joined opens the game
  picker (each game's card on the island).
- **Menu, from any game:** hold a wired button 3 s (`MENU_HOLD_S`), or `q` on the console, or Menu (Home) on the USB
  page. The game pauses and your bar goes green with one red light: move to the red light and pick for the game
  picker; pick green, back, or wait 30 s to carry on.
- **Island Rush: each player sees the island from their own side**, their bar past their nearest row. Move steps
  through every spot they can pick, then the bar; pick picks. Arrows move the cursor directly.
- **Lights on a spot:** 1 light = the middle LED, 2 = the outer two, 3 = all, so it reads the same from every side.
  The cursor lights a spot's empty LEDs dim white and flashes its lit ones.
- **The computer** plays at watch speed: its cursor walks to the spot, the chance shows on its bar, the roll runs.

## On the board

1. Install CircuitPython 10 for the Feather RP2040 SCORPIO (tested on 10.3.1), and from the 10.x bundle into
   `lib/`: `adafruit_neopxl8`, `adafruit_pioasm` and `adafruit_pixelbuf` (or `neopixel` with
   `LED_DRIVER = "neopixel"`).
2. With the board plugged in: `powershell -ExecutionPolicy Bypass -File tools\deploy.ps1`. It compiles `gamehost/`
   and every game to `.mpy` with Adafruit's `mpy-cross` for the board's exact CircuitPython version (downloaded the
   first time), puts every game's source in `games/src/` on the drive to read and change (the board doesn't load
   them; copy a changed one into `games/`, where a `.py` is loaded before the `.mpy`), and copies `code.py` and
   `Lemnos.html`. It writes only what
   changed, removes `.py` copies the new `.mpy` files replace, and never overwrites the drive's `config.py`
   (`-DryRun` says what it would do). Compiling the source on the board itself takes a lot more RAM than running it:
   a big game doesn't fit as `.py`. A small game of your own can just be copied to `games/` as a `.py`. After moving
   to a new CircuitPython version, run it again (`.mpy` files only load on the version they were made for).
3. Wire to `docs/wiring.md`, or change `config.py` to match your wiring.
4. Bring-up: to check every LED, color and address, set `GAME = "testpattern"`: red, green and blue each fill the
   board one LED at a time, rows A to G left to right as seen from seat 1, then the bars seat 1 to 6, so an LED out of
   turn is mapped wrong. Pick pauses; move steps and prints the LED's channel and address. To check every controller by hand, set
   `GAME = "paint"`.
5. Then `code.py` runs the game. The serial console works as up to 6 controllers for testing (m, n, p, b, w/a/s/d,
   q for the game picker; a digit switches controller). A line starting with any other letter is a command for the game, such as
   `time 14:32` for the clock (`GAME = "clock"`); `powershell -File tools\settime.ps1 COM16` sends this computer's time.
   With the radio wired (`radio/README.md`), `radio` lists its players and `radio pair` starts pairing. `/mem`
   prints the free RAM, in any game (the `/` because `m` is a key; the USB page adds it), and `help` lists every
   command there is right now (the board's, the radio's and the running game's, from their `HELP`) and the keys.

## The USB page

Plug the board into a computer and open `Lemnos.html` on the CIRCUITPY drive in **Edge, Chrome or Firefox** (Edge is
already on every Windows PC; Safari doesn't have Web Serial). Press **Connect** and pick the board's port; after
that it connects by itself whenever the page is open and the board is plugged in. Only one program can have the port
open, so close Mu, Thonny or a serial monitor first.

- **The board:** its lights live, as the game draws them (before brightness), about 15 times a second.
- **Game and brightness:** take effect at once and are remembered through power-off (`gamehost/saved.py`, in the
  RP2040's own non-volatile memory, so the drive stays untouched). **Back to config.py's** forgets them. The radio's
  web page sets the same two settings; the last one set wins.
- **New game:** the running game's setup as a form (Island Rush: how many play, each controller's seat and
  color) and **Start**; or **New game at the
  board**, back to the game's setup on the board. A game offers the form with `options()` and `setup()`, the same
  fields the board's lobby uses (`docs/making-games.md`).
- **The clock** is set from the computer's when the page connects.
- **Play from this computer:** a D-pad, Pick, Back and Move, or the keyboard (arrows, Enter, Esc, Space); up to six
  players (`usb-p1`..`usb-p6`). They leave the game when the page closes.
- **Console:** what the board prints, commands for the game, and restarting the board. If the program stops with an
  error, the page says so; **Restart without saved settings** gets out of a saved game that won't run.

The page and the board talk over the same serial console people type on: the page's lines start with `!`, the
board's answers with `@` (`gamehost/usbpage.py` lists them).

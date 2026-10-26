# Lemnos protocol: the radio and the USB page

How the board (the SCORPIO) talks to the radio co-processor and to the USB page. Moved here from the prototype
notes when the board was named Lemnos.

## Radio protocol

The radio (`radio/`, an ESP32) and the SCORPIO talk over a UART: 115200 8N1, 3.3 V, the radio's TX to the
SCORPIO's RX (GPIO1) and back (wiring in `docs/wiring.md`). Text lines ending in `\n` (a `\r` before it is ignored),
at most 160 characters. **Unknown lines are ignored on both sides**, so either side can add messages later; a line
too long is dropped whole. The radio's side is `radio/core/link.c`, the SCORPIO's `circuitpython/gamehost/radio.py`.

Radio to SCORPIO:

| Line | Meaning |
| --- | --- |
| `HELLO 1.0.0` | The radio started (its firmware version), or answers the SCORPIO's `HELLO`. |
| `IN p1 up` | Player slot 1 pressed up. Actions: `up`, `down`, `left`, `right`, `pick`, `back`, `menu` (radio 1.1.0 on: the board's game picker). A held direction repeats on the radio (0.4 s, then every 0.16 s); `pick`, `back` and `menu` come once per press. |
| `CTL p1 connected xbox` | A controller took slot 1. Kinds: `wiimote`, `xbox`, `xac` (Xbox Adaptive Controller), `phone`, `gamepad` (any other Bluepad32 gamepad). A slot that changes hands (rearranged on the web page) is announced again with its new kind. |
| `CTL p1 disconnected` | Slot 1 is empty. |
| `TIME 2026-10-20T14:05:00` | Local time (time zone and daylight saving already applied), sent right as that second starts: after NTP sets the clock, once a minute, after a `HELLO`, when the time zone changes, and at once when the UTC offset changes (daylight saving starts or ends). |
| `SET brightness 6` | Brightness 1-10 on a log scale (5 = 10%, 10 = full, each step x1.58: `lights.step_brightness`), saved on the board; `SET brightness default` = `config.BRIGHTNESS` again. |
| `SET game clock` | Play this game now and at power-up (a name from `GAMES`; saved on the board); `SET game default` = `config.GAME` again. |

SCORPIO to radio:

| Line | Meaning |
| --- | --- |
| `HELLO 2026.10.20` | The board software started (`gamehost.VERSION`). Repeated every 3 s until the radio answers. |
| `STATE game rush` | The game running; sent after the radio's `HELLO` and whenever it changes. |
| `STATE fw 2026.10.20` | The board software's version (as in its `HELLO`); sent after the radio's `HELLO`. |
| `STATE brightness 6` | The brightness setting (1-10 or `default`); sent after the radio's `HELLO` and whenever it changes. |
| `GAMES clock paint rush testpattern` | The games on the board, for the web page's game list; sent after the radio's `HELLO`. |
| `ACK brightness` | A `SET` arrived (sent even if the value was out of range and ignored). |
| `PAIR` / `PAIR off` | Pairing mode on (for a minute) or off: the console's `radio pair`. |

Start-up: whichever side starts second says `HELLO` and the other answers. On the SCORPIO's `HELLO` the radio sends
its own `HELLO`, any setting changed on its page that the board hasn't `ACK`ed yet, `CTL` for every connected slot,
and `TIME` at the next second. The board keeps its own game and brightness (`saved.py`), whether the radio's page or
the USB page set them, and reports them with `STATE`; the radio's page follows those. (Until Oct 20, 2026 the radio
pushed its saved settings at every `HELLO`, which undid changes made on the USB page.) On the radio's `HELLO` the SCORPIO sends `STATE` and `GAMES`. A radio that restarts
while the SCORPIO runs has said `HELLO` first, so the SCORPIO's answer is the first it hears: any line from it counts
as the board being there, and the radio sends `TIME` then. With no radio wired the
SCORPIO keeps saying `HELLO` every 3 s and hears nothing; noise on a floating RX pin is ignored like any unknown line.

Added beyond the first spec (Oct 20, 2026): the radio's own `HELLO`, `GAMES` (so the web page can list the games),
`PAIR` (so a board menu or the console can start pairing), `SET brightness default`, and the `gamepad` kind.

## USB page

`circuitpython/Lemnos.html` (copied to the CIRCUITPY drive; `Salient.html` before the board was named Lemnos) talks
to the board over the USB serial console with Web Serial, in Edge, Chrome or Firefox, straight from the drive. It
speaks the radio's lines (`gamehost/link.py` reads them for both), with `!` in front of each line to the board and `@` in front of each line back, so they share the
console with people typing. On top of the radio's lines: `WATCH on|off` (the lights), `BYE`, `START {json}` (a game
set up on the page: `Game.setup`), `NEWGAME` (the game made afresh, back at its setup on the board), and back
`BOARD`, more `STATE` keys (`brightness`, `default_game`, `default_brightness`), `PLAYERS` and `OPTIONS` (JSON: the
game's setup form, `Game.options`), `SETUP ok` or why not, and `LEDS` (base64, every LED in lights.py's logical
order, as drawn, at most 15 a second). The full list is at the top of `circuitpython/gamehost/usbpage.py`.

**Memory (found Oct 20, 2026, with Salient, the invasion game, which isn't in this repo yet):** with the board
software as `.py` files, Salient no longer fit on the board,
neither at power-up nor switched to: compiling `games/salient/game.py` on the board runs out of RAM (and this
morning's version, which loads, leaves too little for the LED driver). In a bare REPL it loads with 88 KB to spare.
So `circuitpython/tools/deploy.ps1` now compiles `gamehost/` and folder games to `.mpy` (and now one-file
games too, with their sources in `games/src/` on the drive). Even so, a page-started game ran out of memory: in use at
Salient's setup was 138 KB of a heap that tops out near 157 KB (small board). Measured part by part (`gc.mem_alloc`;
`gc.mem_free` misleads, since CircuitPython 10 grows the heap as it goes): Salient 49 KB, NeoPXL8 26 KB (10.5 KB of
it adafruit_pioasm, needed only to build the PIO program, and 3.6 KB a second pixel copy the library keeps when its
brightness isn't 1), geometry 19 KB, controls/hubs/radio/page 18 KB. Fixed: pioasm is unloaded once the driver is
built, lights.py does the dimming itself (the driver stays at 1.0), and the page's lights frames go straight out as
bytes with one allocation (they were five copies) and its setup form is only rebuilt when the game or controllers
change; a MemoryError in page traffic only drops that message. Now 29.7 KB free at setup and a steady 26.3 KB
during computer-against-computer play with the page watching (`mem` on the console prints it). Switching games unloads the old game's modules, so games can
take turns in RAM (an attract mode cycling through games becomes possible). A saved game that won't load or doesn't
fit is forgotten and config.py's game starts instead, so the board can't get stuck on one.

The game and brightness set from either page are saved on the board (`gamehost/saved.py`, the RP2040's NVM) and
used at power-up over `config.py`'s; `SET game default` / `SET brightness default` forget them. Tested Oct 20,
2026 on the small board (COM16): HELLO, the lights (645 bytes a frame), players, settings saved through a restart.

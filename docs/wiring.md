# Salient board wiring

The reference for wiring the board to the Adafruit Feather RP2040 SCORPIO. The software side lives in
`circuitpython/config.py`; if the wiring changes, change it there and nowhere else.

## Seats

Seats are numbered clockwise from the bottom. The bottom is fixed by the build: it's where row G is and where the
wired controller sits. Seat 1 is player one.

| Seat | Side | Coast spots it faces (beachhead in bold) |
| --- | --- | --- |
| 1 | Bottom | G1, **G2, G3**, G4 |
| 2 | Lower left | G1, **F1, E1**, D1 |
| 3 | Upper left | D1, **C1, B1**, A1 |
| 4 | Top | A1, **A2, A3**, A4 |
| 5 | Upper right | A4, **B5, C6**, D7 |
| 6 | Lower right | D7, **E6, F5**, G4 |

## LED channels

One SCORPIO output per run. The 8 outputs are the inner pins of the 2×8 header on the board's short end; the outer
pins are all ground.

| Channel | SCORPIO pin | Runs to | LEDs |
| --- | --- | --- | --- |
| 0 | NEOPIXEL0 (GPIO16) | Island | 111 on the large board, 155 on the small |
| 1 | NEOPIXEL1 (GPIO17) | Seat 1 bar (bottom) | 10 |
| 2 | NEOPIXEL2 (GPIO18) | Seat 2 bar (lower left) | 10 |
| 3 | NEOPIXEL3 (GPIO19) | Seat 3 bar (upper left) | 10 |
| 4 | NEOPIXEL4 (GPIO20) | Seat 4 bar (top) | 10 |
| 5 | NEOPIXEL5 (GPIO21) | Seat 5 bar (upper right) | 10 |
| 6 | NEOPIXEL6 (GPIO22) | Seat 6 bar (lower right) | 10 |
| 7 | NEOPIXEL7 (GPIO23) | Spare | – |

All 8 outputs update together (NeoPXL8), so the whole board refreshes in about 3.5 ms (about 5 ms on the small board). The library gives every
channel the island's length in memory; the bars just use their first 10.

LEDs are 5 V addressable (WS2812B-type, GRB). The color order is `PIXEL_ORDER` in `config.py`.

### Wired differently

`config.py` says where each part starts, as (channel, LED): `ISLAND_AT` for the island's run (the serpentine
below, from the corner hex that `ISLAND_START` names) and `BARS_AT` for each seat's bar (LED 1). The table above
is the default. `LED_DRIVER` picks what
drives them:

- `"neopxl8"` (default): 8 outputs at once from `LED_PIN` on; a channel is one output.
- `"neopixel"`: one strand on `LED_PIN`, on any CircuitPython board (a Pico, say). There's only channel 0, so chain
  the bars after the island: `ISLAND_AT = (0, 0)`, `BARS_AT = ((0, 111), (0, 121), … (0, 161))` (from 155 on the
  small board). One strand of 171 LEDs takes about 5 ms to update, which is fine at 40 frames a second.
- Your own, for other LED hardware: see `circuitpython/gamehost/drivers.py`.

### Island run (channel 0)

#### Names

Everything is named as seen from seat 1 (Player One, at the bottom):

- **Rows** A to G, from the farthest from seat 1 (A) to the nearest (G). They have 4, 5, 6, 7, 6, 5 and 4 hexes.
- **Hexes:** the row and 1 to n, left to right: A1–A4, B1–B5, C1–C6, D1–D7 (D4 is the center), E1–E6, F1–F5,
  G1–G4.
- **Lines** (small board): the vertical edges in a row, each with an LED under it. A row has one more line than
  hexes, also counted from 1, left to right: line B1 is row B's left end, line Bk is just left of hex Bk, and line
  B6 is the right end. So hex Bk sits between lines Bk and Bk+1. The slanted edges between rows have no LEDs.

Games use these names (`lights.spot("B3", …)`, `lights.line("B4", …)`) and never see the strip order below.

#### The run

`BOARD` in `config.py` says which board it is. Both are the same serpentine on the same channel: the data enters at
the right end of row G (G4, the bottom right as seen from seat 1), runs along it right to left, and loops from the
end of each row to the same end of the next, up the board to row A. So rows G, E, C and A run right to left, and F,
D and B left to right. The small board just has the line LEDs in the chain too.

**Large board** (60 LEDs/m, 111 LEDs): 3 LEDs per hex.

| Row | Run order | LEDs |
| --- | --- | --- |
| G | G4 → G1 | 0–11 |
| F | F1 → F5 | 12–26 |
| E | E6 → E1 | 27–44 |
| D | D1 → D7 | 45–65 |
| C | C6 → C1 | 66–83 |
| B | B1 → B5 | 84–98 |
| A | A4 → A1 | 99–110 |

**Small board** (144 LEDs/m, 155 LEDs): 3 LEDs per hex with a line LED on each side, so a row of n hexes has
4n + 1 LEDs. Line G1 (left of G1) loops to line F1 (left of F1).

| Row | Run order | LEDs |
| --- | --- | --- |
| G | line G5, G4, line G4, G3, line G3, G2, line G2, G1, line G1 | 0–16 (17) |
| F | line F1, F1, line F2, … F5, line F6 | 17–37 (21) |
| E | line E7, E6, line E6, … E1, line E1 | 38–62 (25) |
| D | line D1, D1, line D2, … D7, line D8 | 63–91 (29) |
| C | line C7, C6, line C6, … C1, line C1 | 92–116 (25) |
| B | line B1, B1, line B2, … B5, line B6 | 117–137 (21) |
| A | line A5, A4, line A4, … A1, line A1 | 138–154 (17) |

A hex's 3 LEDs follow the run, so on G, E, C and A a hex's first LED on the strip is its right one (as seen from
seat 1).

**Other corners** (`ISLAND_START` in `config.py`): the run can start at any corner hex, `"G4"` (the default),
`"A1"`, `"A4"` or `"G1"`. From A1 (the original wiring) it's the whole run above backward: row A first, A1 → A4 on
LEDs 0–11, then B5 → B1, and so on down to G1 → G4 on 99–110; on the small board line A1 is LED 0 and line A5 loops
to line B6. The software handles all of this; just follow the strip. `tools/test_host.py` checks every LED of both boards
against these tables; on the board, `GAME = "testpattern"` in `config.py` lights them in order to check the wiring.

### Bars (channels 1–6)

10 LEDs each. LED 1 is at the player's left as they sit facing the island.

## Power

All 171 LEDs (215 on the small board) at full white draw about 10 A (13 A). The software caps the LED current to `POWER_LIMIT_A` in `config.py`
(4 A by default) by dimming the whole frame when needed; set it to `None` for full brightness on a supply that can
take it. Feed 5 V to the strips directly (not through the Feather), with the grounds tied together.

## Controls

Every player uses three actions: move, pick and back. Any mix of input devices can produce them; `config.py` lists
them. See [controllers.md](controllers.md) for the device types and the I2C protocol for outboard controller boards.

The default wired controller, at seat 1:

| Input | Pin | Does |
| --- | --- | --- |
| Encoder A / B | D24 / D25 (GPIO24 / 25) | Turn clockwise = move, counterclockwise = move back |
| Encoder push | D9 | Pick |
| Button | D10 | Back |

Switches short the pin to ground (internal pull-ups are on). An encoder's two pins must be consecutive GPIOs
(the RP2040 encoder driver needs that); D24/D25, D9/D10, D11/D12, SCK/MO (GPIO14/15) and A0/A1 all are.

### Free inputs

17 general inputs are free with the island, six bars and the I2C bus in use:

| Pins | GPIO | Notes |
| --- | --- | --- |
| A0–A3 | 26–29 | Can also read analog, e.g. a resistor-ladder switch box |
| D24, D25 | 24, 25 | Default encoder |
| D5, D6 | 5, 6 | |
| D9–D12 | 9–12 | D9, D10 default encoder push and button |
| SCK, MO, MI | 14, 15, 8 | Free while nothing uses SPI |
| TX, RX | 0, 1 | Free; the serial console runs over USB |

Avoid D13 (red LED on it), D4 (onboard status NeoPixel) and the BOOT button (GPIO7). SDA/SCL (GPIO2/3, the STEMMA QT
port) are the I2C bus for controller boards, and for an RTC chip (DS3231, PCF8523 or DS1307 at 0x68, set in
`config.RTC`) that keeps the clock's time through power-off. NEOPIXEL7 is output-only (level shifter), so it stays
the spare LED channel.

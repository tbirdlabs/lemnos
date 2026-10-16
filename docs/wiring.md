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
| 0 | NEOPIXEL0 (GPIO16) | Island | 111 |
| 1 | NEOPIXEL1 (GPIO17) | Seat 1 bar (bottom) | 10 |
| 2 | NEOPIXEL2 (GPIO18) | Seat 2 bar (lower left) | 10 |
| 3 | NEOPIXEL3 (GPIO19) | Seat 3 bar (upper left) | 10 |
| 4 | NEOPIXEL4 (GPIO20) | Seat 4 bar (top) | 10 |
| 5 | NEOPIXEL5 (GPIO21) | Seat 5 bar (upper right) | 10 |
| 6 | NEOPIXEL6 (GPIO22) | Seat 6 bar (lower right) | 10 |
| 7 | NEOPIXEL7 (GPIO23) | Spare | – |

All 8 outputs update together (NeoPXL8), so the whole board refreshes in about 3.5 ms. The library gives every
channel the island's length in memory; the bars just use their first 10.

LEDs are 5 V addressable (WS2812B-type, GRB). The color order is `PIXEL_ORDER` in `config.py`.

### Island run (channel 0)

A serpentine, 3 LEDs per spot, starting at A1 (top left):

| Row | Spots in run order | LEDs |
| --- | --- | --- |
| A | A1 → A4 | 0–11 |
| B | B5 → B1 | 12–26 |
| C | C1 → C6 | 27–44 |
| D | D7 → D1 | 45–65 |
| E | E1 → E6 | 66–83 |
| F | F5 → F1 | 84–98 |
| G | G1 → G4 | 99–110 |

Each spot's 3 LEDs follow the run, so on B, D and F (running left) a spot's first LED is its right one. The software
handles that; just follow the strip.

### Bars (channels 1–6)

10 LEDs each. LED 1 is at the player's left as they sit facing the island.

## Power

All 171 LEDs at full white draw about 10 A. The software caps the LED current to `POWER_LIMIT_A` in `config.py`
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
port) are the I2C bus for controller boards. NEOPIXEL7 is output-only (level shifter), so it stays the spare LED
channel.

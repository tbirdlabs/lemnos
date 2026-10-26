# Lemnos, the Open, Accessible Game Board

An open hex LED game board by Thunderbird Labs: an island of 37 hexes, six seats with a 10-light bar each, and any
mix of controllers: one switch, a pedal, three buttons, a D-pad, a knob, Bluetooth gamepads (Wiimote, Xbox, the Xbox
Adaptive Controller) or a phone. Built for the MakerWorld "Make for Good" PlayforAll brief: every game plays with
one switch, and everything a game knows is readable from the board's lights.

Games are plug-ins on the board's drive. The board itself handles the game picker, setup, menus and controllers, so
a game only has to know its rules (see [docs/making-games.md](docs/making-games.md)).

- **Island Rush**, the first game: up to 6 players race through the jungle to the taco truck in the middle of the
  island, with tigers on the way. The computer plays any seat no one takes. Rules in [docs/rules/](docs/rules/).
- Attract screens and wall decorations: an analog clock, a forest fire, fireflies, the northern lights, rain on a
  pond. Plus `paint` (the small example game) and a test pattern for bring-up.
- **Salient**, an island invasion strategy game, is being worked on. It isn't in this repository yet.

The name: Lemnos is the island where Hephaestus, the maker god, landed when he was thrown from Olympus, and was
taken in.

## What's here

- `circuitpython/`: the board software for the Adafruit Feather RP2040 SCORPIO. `gamehost/` (lights, controllers,
  the lobby, the host; knows no game), `games/`, `Lemnos.html` (the USB page) and `tools/` (tests, the Island Rush
  simulator, deploying to the board). Start with its [README](circuitpython/README.md).
- `radio/`: firmware for the optional radio co-processor, an ESP32 that adds Bluetooth controllers, phones as
  controllers, a settings page and the time of day. See its [README](radio/README.md).
- `docs/`: [wiring](docs/wiring.md), [controllers](docs/controllers.md) (the types, and the I2C protocol),
  [the radio and USB page protocol](docs/protocol.md), [making games](docs/making-games.md),
  [build notes](docs/build-notes.md) (the bugs and how they were run down), and `rules/`: the rules, one frozen
  export per version. Older exports, from before the board had its name, call it the Salient board.

## Tests (desktop, from `circuitpython/`)

```
py -3 tools/test_host.py        the board's parts and the small games
py -3 tools/test_rush.py        Island Rush: rules, and whole games through the board's controls
py -3 tools/test_radio.py       the radio link, and a two-player Island Rush played over it
py -3 tools/test_usbpage.py     the USB page's side on the board
node tools/test_page.js         the USB page itself, without a browser
py -3 ../radio/test/run_tests.py   the radio's portable C core
```

## Versions

Board software releases are tagged `board-<version>` (`gamehost.VERSION`, by date), with `-rcN` for a release
candidate. Island Rush rules versions are tagged `rush-vX.Y`.

## License

- **Software** (`circuitpython/`, `radio/`, the tests and tools): MIT. See [LICENSE](LICENSE). The radio firmware
  is built on third-party libraries with their own licenses, listed in [radio/README.md](radio/README.md#license).
- **Rules** (`docs/rules/`) and other documentation, and the board's CAD when it's added: CC BY-SA 4.0, the same
  as the Printables listing. See [LICENSE-CC-BY-SA-4.0.txt](LICENSE-CC-BY-SA-4.0.txt).

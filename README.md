# Salient

A light-up island strategy game for a hex LED board, by Thunderbird Labs. Built for the MakerWorld "Make for Good"
PlayforAll brief: playable with one switch, a pedal, three buttons or a D-pad, and everything the game knows is
readable from the board's lights.

- `index.html` – browser prototype of the board (Invasion, Defender and Island Rush, all six seats), with a developer panel (rules settings, AI-vs-AI simulator, notes)
  behind `#debug` in the address. Open it from disk or from the IIS share.
- `circuitpython/` – the board software for the Feather RP2040 SCORPIO: host, lights, controllers and the game (see its README).
- `docs/wiring.md`, `docs/controllers.md` – how to wire the board, and the controller types and I2C protocol.
- `docs/rules/` – the rules, one frozen export per version.
- `NOTES.md` – prototype notes: file map, engine layout, settings, simulator results, difficulty and volcano tests.

```
run-tests
run-sim --games 4000
```

Island Rush: `sim-rush.js` (AI-vs-AI by player count). Browser UI: `test-ui.js`. Board UI: `py -3 circuitpython/test_board.py`.

## Versions

Earlier prototypes are tagged in git rather than kept as folders: `v0.7` (61 tiles), `v0.8` (odds table, Mass,
backfill), `v0.9-bases` (v0.9 with bases and experiment settings), `v0.10` (v0.10 plus the sim-tested
settings), `v0.11` (the rules doc for that code). `git checkout v0.8` gets a runnable copy.

## License

- **Software** (the prototype, simulator, tests and `circuitpython/`): MIT. See [LICENSE](LICENSE).
- **Rules** (`docs/`) and other documentation, and the board's CAD when it's added: CC BY-SA 4.0, the same as the
  Printables listing. See [LICENSE-CC-BY-SA-4.0.txt](LICENSE-CC-BY-SA-4.0.txt).

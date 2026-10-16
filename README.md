# Salient

A light-up island strategy game for a hex LED board, by Thunderbird Labs. Built for the MakerWorld "Make for Good"
PlayforAll brief: playable with one switch, a pedal, three buttons or a D-pad, and everything the game knows is
readable from the board's lights.

- `index.html` – browser prototype of the board, with a developer panel (rules settings, AI-vs-AI simulator, notes)
  behind `#debug` in the address. Open it from disk or from the IIS share.
- `circuitpython/` – the engine and AI ported to CircuitPython for the Feather RP2040 SCORPIO (see its README).
- `docs/rules/` – the rules, one frozen export per version.
- `NOTES.md` – prototype notes: file map, engine layout, settings, simulator results, difficulty and volcano tests.

```
run-tests
run-sim --games 4000
```

## Versions

Earlier prototypes are tagged in git rather than kept as folders: `v0.7` (61 tiles), `v0.8` (odds table, Mass,
backfill), `v0.9-bases` (v0.9 with bases and experiment settings), `v0.10` (v0.10 plus the sim-tested
settings), `v0.11` (the rules doc for that code). `git checkout v0.8` gets a runnable copy.

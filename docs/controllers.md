# Salient controllers

Every player plays with the same few actions: **move**, **pick** and **back**. Some controllers add **move back**
(an encoder turned the other way) or a D-pad (**up**, **down**, **left**, **right**). What works for one player may
not work for another, so the board takes any mix of devices, and a game never knows which device an action came
from. It only knows which controller sent it, and which actions that controller can send.

Controllers are listed in `circuitpython/config.py`. Three kinds of source feed them:

- **Wired inputs** on the SCORPIO's free pins (17 of them; see [wiring.md](wiring.md)): `gamehost/inputs.py`.
- **Outboard controller boards** on the I2C bus (an ESP32 with Bluepad32 for Bluetooth gamepads, a Pico reading a
  switch box, and so on), chained on the STEMMA QT port: the `"i2c"` hub in `gamehost/hubs.py`.
- **The USB serial console**, for testing: up to 6 virtual controllers: the `"console"` hub.

`CONTROLLER_HUBS` in `config.py` lists the hubs to start; take one out to turn it off. Games see none of this, only
controllers and actions ([making-games.md](making-games.md)).

## Wired inputs

| Type | Wiring | Gives | Settings |
| --- | --- | --- | --- |
| `button` | One switch to ground | its `does` action on press | `hold`: a second action for a long press (`hold_s`, default 0.8 s) |
| `encoder` | Rotary encoder on two consecutive GPIOs | move (clockwise), move back | `reverse`, `divisor` |
| `scan` | One switch to ground | pick; the board steps (move) every `every` seconds | `every` (default 1.5 s), `hold` |
| `ladder` | Several switches on one analog pin through resistors | each band's action | `bands`: (low V, high V, action) |

A controller is a list of inputs plus a seat: `{"name": ..., "seat": 1, "inputs": [...]}`. `seat` is the side it
sits at (1–6, clockwise from the bottom), or `None` if its player chooses a side when joining.

The default, a rotary encoder and one button:

```python
{"name": "wired", "seat": 1, "inputs": [
    {"type": "encoder", "a": "D24", "b": "D25"},          # turn = move
    {"type": "button", "pin": "D9", "does": "pick"},      # encoder push
    {"type": "button", "pin": "D10", "does": "back"},
]}
```

A controller without back (a single switch, say) still works: the game adds a way-out stop to each scan, so
picking it does what back would.

To add a new kind of input, write a class with `can` (the set of actions it can give) and `poll(now, emit)` (call
`emit(action)` for each action since the last poll), made from its line in `config.py` as a dict. Put it in its own
file on CIRCUITPY and use `"file.Class"` as its type, e.g. `{"type": "footpedal.Pedal", "pin": "A3"}`; or add it to
`INPUTS` in `gamehost/inputs.py`. The classes there are the examples to copy.

A source that brings any number of controllers of its own (Bluetooth straight to the board, say) is a hub: a class
made with the `Controls`, with `poll(now, emit)` calling `emit(controller, action)`, getting its controllers from
`controls.get(id, name, seat, can)` and calling `controls.remove(controller)` when one goes away. Name it in
`CONTROLLER_HUBS` the same way.

## I2C controller boards (protocol v1)

The SCORPIO is the I2C controller on its STEMMA QT port (SDA/SCL, 100 kHz). Each controller board is an I2C target
at an address from 0x30 to 0x3F; give each board on the chain its own address. The SCORPIO looks for boards at
power-up and every 5 seconds, so a board can be plugged in during setup.

About 40 times a second the SCORPIO reads **8 bytes** from each board:

| Byte | Meaning |
| --- | --- |
| 0 | `0x10 | n`: protocol version 1 in the high nibble, n = number of events that follow (0–7) |
| 1 … n | One event each: `pad << 4 | code` |
| n+1 … 7 | Anything (ignored) |

After a read, the board drops the events it sent. If more than 7 are waiting, it sends the oldest 7 and the rest
next time. A board answering with anything other than version 1 in byte 0 is ignored.

`pad` (0–15) tells apart several controllers on one board, such as several Bluetooth gamepads on one ESP32. Each
(board, pad) pair is its own controller to the game.

| Code | Event |
| --- | --- |
| 1 | move |
| 2 | move back |
| 3 | pick |
| 4 | back |
| 5 | up |
| 6 | down |
| 7 | left |
| 8 | right |
| 9 | This pad is a single switch (no back); send once when it connects |
| 15 | This pad disconnected (the game hears `controller_removed`; the pad's next event brings it back) |
| 0, 10–14 | Reserved |

How a board maps its buttons is up to the board. For a gamepad, the suggested mapping is: D-pad or left stick =
up/down/left/right, A = pick, B = back, and the shoulder buttons = move back / move.

For a single switch on a board: send code 9 once when it connects, then send move on a timer (the scan) and pick
when the switch closes. Code 9 tells the game the pad has no back, so the game adds its way-out stops.

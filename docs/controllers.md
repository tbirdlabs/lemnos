# Lemnos controllers

Every player plays with the same few actions: **move**, **pick** and **back**. Some controllers add **move back**
(an encoder turned the other way) or a D-pad (**up**, **down**, **left**, **right**). What works for one player may
not work for another, so the board takes any mix of devices, and a game never knows which device an action came
from. It only knows which controller sent it, and which actions that controller can send.

One more action, **menu**, is the board's own: from any game, at any time, it asks for the game picker. It's made
hard to send by accident (a wired switch held for `MENU_HOLD_S`, 3 s by default), and then the board asks again: the
player's bar turns green with one red light, and only picking the red light leaves the game. Picking green, back,
or waiting 30 s returns to the game, which waited meanwhile. Games never see menu.

Controllers are listed in `circuitpython/config.py`. Four kinds of source feed them:

- **Wired inputs** on the SCORPIO's free pins (see [wiring.md](wiring.md)): `gamehost/inputs.py`.
- **The radio**, an ESP32 on the TX/RX pins: Bluetooth controllers (Wiimote, Xbox, Xbox Adaptive Controller) and
  phones, up to six players: the `"radio"` hub in `gamehost/radio.py` ([below](#the-radio)).
- **Outboard controller boards** on the I2C bus (a Pico reading a switch box, and so on), chained on the STEMMA QT
  port: the `"i2c"` hub in `gamehost/hubs.py`.
- **The USB page** (`Lemnos.html` on the CIRCUITPY drive, in Edge, Chrome or Firefox): an on-screen D-pad and the
  keyboard, up to six players (`usb-p1`..`usb-p6`), through the `"console"` hub (`gamehost/usbpage.py`).
- **The USB serial console**, for testing: up to 6 virtual controllers: the `"console"` hub.

`CONTROLLER_HUBS` in `config.py` lists the hubs to start; take one out to turn it off. Games see none of this, only
controllers and actions ([making-games.md](making-games.md)).

## Wired inputs

| Type | Wiring | Gives | Settings |
| --- | --- | --- | --- |
| `button` | One switch to ground | its `does` action on press; menu when held `MENU_HOLD_S` | `hold`: a second action for a long press (`hold_s`, default 0.8 s) |
| `encoder` | Rotary encoder on two consecutive GPIOs | move (clockwise), move back | `reverse`, `divisor` |
| `scan` | One switch to ground | pick; the board steps (move) every `every` seconds; menu when held `MENU_HOLD_S` | `every` (default 1.5 s), `hold` |
| `ladder` | Several switches on one analog pin through resistors | each band's action; menu when any is held `MENU_HOLD_S` | `bands`: (low V, high V, action) |

A controller is a list of inputs plus a seat: `{"name": ..., "seat": 1, "inputs": [...]}`. `seat` is the side it
sits at (1–6, clockwise from the bottom), or `None` if its player chooses a side when joining.

A controller can carry a bar of its own: `"bar": 1` names the bar built into it (its place in `BARS_AT`). The bar
goes with the controller, so it always shows its player's lights. If the player picks a different seat in a game's
setup, that seat is drawn on the controller's bar, and the bar that seat had takes over the seat the controller came
from. Left out, the first wired controller carries bar 1 and the rest carry none.

The default, a rotary encoder and one button, with bar 1:

```python
{"name": "wired", "seat": 1, "bar": 1, "inputs": [
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

## The radio

The radio co-processor (`radio/` in this repo; setup and flashing in [radio/README.md](../radio/README.md)) brings
the controllers that need a radio: Bluetooth gamepads, and phones over WiFi. It sorts them into **player slots**
p1 to p6, and each slot is one controller to the game (`radio-p1`, named like "player 1 (Xbox)"), whatever device
is in it. A controller keeps its slot when it reconnects, and the slots can be rearranged on the radio's web page.
Every radio controller sends only up, down, left, right, pick, back and (from radio firmware 1.1.0) menu; the game
never learns the device.

| Controller | Moves | Pick | Back | Menu |
| --- | --- | --- | --- | --- |
| Wiimote, upright in one hand (the default) | D-pad | A | B (the trigger) | Home |
| Wiimote, sideways in two hands (chosen per Wiimote on the radio's page) | D-pad | 2 | 1 | Home |
| Xbox One (model 1708, current firmware) or Series | D-pad or left stick | A | B | Xbox button or Menu (Start) |
| Xbox Adaptive Controller | D-pad, or switches in its 3.5 mm jacks set to D-pad | A | B | Xbox button or Menu |
| Phone (the radio's web page `/pad`) | the on-screen D-pad | PICK | BACK | Menu (top right) |
| Other Bluetooth gamepads Bluepad32 knows | D-pad or left stick | A (bottom face button) | B (right) | Home / PS or Start |

A held direction repeats, the same on the D-pad and the stick: once at once, again after 0.4 s, then every 0.16 s.
The stick has a deadzone and doesn't flicker between two directions on a diagonal. The Adaptive Controller's jacks
arrive as its A, B and D-pad, so single switches work through it: assign a jack to A and the switch picks.

A radio controller has no `seat` (its player chooses a side when joining) unless `RADIO_SEATS` in `config.py` gives
the slots seats. Pairing mode (a minute, for new controllers) starts from the web page, the radio's own button, or the
console: `radio pair` (`radio` alone lists who's connected). Without a radio, the hub sends a hello every few seconds
and nothing else happens.

The board also takes settings from the radio's web page (brightness, the game to play; the host applies them) and
the time of day (the clock). The UART protocol is in [docs/protocol.md](protocol.md#radio-protocol).

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
| 10 | menu (back to the game picker; the board asks first): a long press, or a Home / Start button |
| 15 | This pad disconnected (the game hears `controller_removed`; the pad's next event brings it back) |
| 0, 11–14 | Reserved |

How a board maps its buttons is up to the board. For a gamepad, the suggested mapping is: D-pad or left stick =
up/down/left/right, A = pick, B = back, the shoulder buttons = move back / move, and Home or Start = menu.

For a single switch on a board: send code 9 once when it connects, then send move on a timer (the scan) and pick
when the switch closes. Code 9 tells the game the pad has no back, so the game adds its way-out stops.

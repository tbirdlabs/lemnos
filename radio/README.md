# Salient radio co-processor

The SCORPIO (Feather RP2040) has no radio, so a separate ESP32 board handles everything wireless and talks to it over
three wires:

- **Bluetooth controllers:** Wiimote, Xbox One (1708, current firmware) and Series controllers, the Xbox Adaptive
  Controller, and most other Bluetooth gamepads (through [Bluepad32](https://github.com/ricardoquesada/bluepad32)).
- **Phones as controllers:** a D-pad, Pick and Back on a web page, over WiFi.
- **A settings page** on your phone: time zone, brightness, the game, controllers and their player slots, WiFi.
- **The time of day** from the internet (NTP), with the time zone and daylight saving worked out on the radio.

Up to six players (p1 to p6; up to four of them Bluetooth). Every controller becomes the same three things, move
(up/down/left/right), pick and back, so games never know what anyone is holding. The board runs as before with no
radio attached. Wiring is in [docs/wiring.md](../docs/wiring.md#the-radio); the protocol on the wire is in
[NOTES.md](../NOTES.md#radio-protocol).

## Boards

| Board | Firmware file | UART to the SCORPIO | Notes |
| --- | --- | --- | --- |
| ESP32 DevKit (any ESP32-WROOM-32 dev board) | `salient-radio-esp32dev-…` | GPIO17 TX, GPIO16 RX | The reference board |
| NodeMCU-32S (Ai-Thinker ESP-32S) | `salient-radio-nodemcu-32s-…` | GPIO17 TX, GPIO16 RX | Same pins as the DevKit, in a different order on the header: go by the silkscreen labels |
| LilyGO TTGO T-Display | `salient-radio-ttgo-t-display-…` | G25 TX, G26 RX | GPIO16 drives its screen, so the UART moves. The screen shows the setup network or salient.local and the address, the time, pairing, and who's playing |
| Pico W / Pico 2 W | (build it: `pico/`) | GP4 TX, GP5 RX | Experimental: Bluetooth controllers only for now, no WiFi (see [Pico W](#pico-w-experimental)) |

**Only the original ESP32 works.** The ESP32-S2, S3, C3 and C6 have no Bluetooth Classic, which the Wiimote needs
(the S2 has no Bluetooth at all). Boards sold as "ESP32-S3 DevKit" and the like won't do; look for ESP32-WROOM-32 or
ESP32-D0WD on the chip.

Wire the radio's TX to the SCORPIO's RX, its RX to the SCORPIO's TX, and ground to ground. Power it from the board's
5 V LED supply into VIN (5V on the T-Display). Most dev boards have a diode between USB and VIN, but not all: if
you're not sure, take the 5 V wire off while the radio is plugged into a computer.

## Flashing (no toolchain needed)

Each release has two files per board:

- `salient-radio-<board>-<version>.bin`: **first install**. Bootloader, partition table and firmware in one file,
  written at address **0x0**. It erases the settings, WiFi network and paired controllers.
- `salient-radio-<board>-<version>-update.bin`: **updates**. The firmware alone, written at **0x10000**. Keeps the
  settings, WiFi network and paired controllers.

`SHA256SUMS.txt` lists their checksums.

**In a browser** (Chrome or Edge on a computer): open [Espressif's web flasher](https://espressif.github.io/esptool-js/),
plug in the radio, press **Connect** and pick its port. Under Flash Address enter `0x0` (or `0x10000` for an update
file), choose the file, and press **Program**. When it's done, press the board's EN/RST button (or unplug it and
plug it back in).

**With esptool** (`pip install esptool`):

```
esptool --chip esp32 --port COM17 write-flash 0x0 salient-radio-ttgo-t-display-1.0.0.bin
esptool --chip esp32 --port COM17 write-flash 0x10000 salient-radio-ttgo-t-display-1.0.0-update.bin
```

Use your port (`/dev/ttyUSB0` on Linux, `/dev/cu.usbserial-…` on a Mac). Older esptool (v4) spells it
`esptool.py … write_flash`. If it can't connect, hold the board's BOOT button while it starts connecting.

## First setup

1. Power it up. With no WiFi network saved it opens its own: **Salient-XXXX** (the T-Display shows the name).
2. Join that network on your phone. The settings page opens by itself; if it doesn't, go to `http://192.168.4.1/`.
3. Under **WiFi**, press **Scan**, pick your network, type the password, and press **Join and restart**.
4. On your home network it's at **http://salient.local/** (or the address on the T-Display's screen, or in your
   router's device list). Android phones without mDNS need the address.

If the saved network isn't found within 20 seconds of power-up, the setup network opens again (the radio keeps
trying the saved one, and closes the setup network a minute after it gets on). **Forget WiFi** on the page, or
holding the radio's button (BOOT on a dev board, either button on the T-Display) for 10 seconds, clears it.

## Controllers

**Pairing:** press **Pair a controller** on the page, press the radio's button (BOOT, or either T-Display button),
or type `radio pair` on the SCORPIO's console. Pairing mode lasts a minute; while it's on, any gamepad that looks for
a host can connect. With nothing paired yet, the radio starts in pairing mode. Outside pairing mode only the
controllers it knows can connect.

| Controller | To pair | After that | Moves | Pick | Back |
| --- | --- | --- | --- | --- | --- |
| Xbox One (1708) or Series | Turn it on, then hold the small pair button on top until the Xbox button flashes fast | Press the Xbox button | D-pad or left stick | A | B |
| Xbox Adaptive Controller | The same, with its pair button on the top edge | Its Xbox button | D-pad, or switches in the jacks set to D-pad | A | B |
| Wiimote, upright (one hand) | Press the red SYNC button under the battery cover | Any button | D-pad | A | B (the trigger) |
| Wiimote, sideways (two hands) | The same; then choose "Two hands" for it on the page | Any button | D-pad | 2 | 1 |
| Phone | Open `http://salient.local/pad` (or **Play from this phone**) | Open the page again | On-screen D-pad | PICK | BACK |

- **Xbox controllers** need current firmware: update them from the Xbox Accessories app (Windows or an Xbox) if they
  won't pair. Firmware 5 and later uses Bluetooth LE, which is what the radio expects.
- **Wiimote:** held upright in one hand unless you choose otherwise: each Wiimote's row on the page has a choice of
  grip ("One hand" or "Two hands, sideways"), remembered for that Wiimote. A Nunchuk's stick moves too. Pairing with 1
  and 2 held also works, but then it won't reconnect by itself; pair with SYNC. Its LEDs show its player slot.
- **Adaptive Controller:** its 3.5 mm jacks arrive as its A, B and D-pad buttons, so single switches and other
  assistive switches work through it.
- **Phones** need no pairing. The page keeps an id in the phone's browser, so a phone comes back to the same slot.
  A phone that turns its screen off leaves the game; open the page again to rejoin.

**Player slots:** each controller plays in a slot, p1 to p6, and keeps it when it reconnects. On the page, the
select beside each controller moves it to another slot (swapping with whoever is there). **Forget** removes a
controller and its pairing; it has to pair again to come back. A slot on the radio is one controller to the board's
games ("player 1 (Xbox)"); see [docs/controllers.md](../docs/controllers.md#the-radio).

A held direction repeats like a key held down: once, again after 0.4 s, then every 0.16 s. The stick has a deadzone,
and a diagonal doesn't flicker between two directions.

## Settings and time

The page's **Board** section sets the game at power-up, the brightness (1–10 on a log scale, 5 = 10%, or the
board's own `config.py` value), and the time zone. They're saved on the radio and sent to the SCORPIO whenever it
starts, so they survive both boards restarting. Changing the game switches the board to it at once.

The time comes from the internet once the radio is on WiFi, turned into local time with the chosen zone's rules
(daylight saving included; the zones come from the IANA time zone database). The radio sends it to the SCORPIO right
on the second, once a minute and whenever it changes, and the SCORPIO writes it to its RTC chip if it has one, so the
clock keeps time through power-off even without the radio. The SCORPIO does no time zone math.

## The console

The radio's USB serial port (115200) prints what it's doing and takes commands (`help` lists them all, including
Bluepad32's own):

| Command | Does |
| --- | --- |
| `status` | Settings, network, time, controllers, the SCORPIO link |
| `link on` / `link off` | Print every line to and from the SCORPIO |
| `pair` / `pair off` | Pairing mode |
| `forget <id>` / `forget all` | Forget a controller (or all), dropping its Bluetooth pairing |
| `faketime 2026-11-01T06:59:30Z` | Set the clock to this UTC time and stop NTP, to watch a daylight saving change |
| `ntp` | Back to internet time |
| `fakepad <slot> connect xbox`, `fakepad <slot> up`, `… pick`, `… disconnect` | Act as a controller, to test the SCORPIO without one |
| `wifi <ssid> [password]`, `wifi_forget` | Join a network, or forget it (both restart) |

To watch a fall-back change in US Central time: `link on`, then `faketime 2026-11-01T06:59:50Z`. The radio sends
`TIME 2026-11-01T01:59:50`, and at 07:00:00 UTC `TIME 2026-11-01T01:00:00` at once.

## Building

The firmware is C on ESP-IDF 5.4 with Bluepad32 4.2.0 as components, built with PlatformIO (the pioarduino
platform). ESP-IDF rather than Arduino: Bluepad32's own interface is C (its "custom platform"), ESP-IDF has
everything else built in (the web server with WebSockets, mDNS, NTP, flash storage, the ST7789 display driver), and
the same C core then builds for the Pico W against the Pico SDK.

```
python tools/get_bluepad32.py        (once: Bluepad32 4.2.0 + its BTstack, patched, into ~/.salient-radio)
pio run                              (all three boards; or -e esp32dev, -e nodemcu-32s, -e ttgo-t-display)
pio run -e ttgo-t-display -t upload --upload-port COM17
python tools/make_release.py         (the files in dist/)
```

On Windows, `build.cmd` does the same (`build ttgo-t-display -t upload --upload-port COM17`). It copies the source
to `%USERPROFILE%\.salient-radio\src` first, because ESP-IDF can't build from a network share. Run it from cmd or
PowerShell, not Git Bash: ESP-IDF's tool installer refuses MSYS shells. `tools/term.py COM17 --reset` shows the boot
log.

| Where | What |
| --- | --- |
| `core/` | Portable C, no platform code: the protocol (`link.c`), controllers to actions with the deadzone and repeat (`pads.c`), known controllers and player slots (`known.c`), time zones (`tz.c`, `tz_zones.inc` from `tools/gen_tz.py`) |
| `shared/` | Bluetooth through Bluepad32 (`bt.c`): who may connect, each controller's kind and buttons. Both builds use it |
| `main/` | The ESP32 build: `hub.c` (the shared state and the UART link), `net.c` (WiFi, the setup network, mDNS), `web.c` (the pages, the API, the phone's WebSocket), `clock.c` (NTP, TIME lines), `display.c` (T-Display), `buttons.c`, `store.c` (flash), `console.c`, `board.h` (pins per board) |
| `web/` | `index.html` (settings) and `pad.html` (the phone controller), built into the firmware |
| `pico/` | The Pico W build (experimental) |
| `test/` | `run_tests.py`: builds `core/` with any C compiler (or `pip install ziglang`) and tests it; checks every time zone against the IANA database to the second, 2026–2036; writes `transcript.txt` for the SCORPIO side's tests |

The SCORPIO side is `circuitpython/gamehost/radio.py`, tested by `circuitpython/tools/test_radio.py` (which also plays
a whole two-player Salient game through the radio's lines).

## Pico W (experimental)

`pico/` builds the same Bluetooth layer and core for the Pico W and Pico 2 W with the Pico SDK (2.1 or later; see
`pico/README.md`). For now it does Bluetooth controllers, player slots and pairing (its BOOTSEL button, or `radio
pair` from the SCORPIO) over the same UART protocol, on GP4 (TX) and GP5 (RX). No WiFi yet: no settings page,
phone controllers or time. It's allowed to lag behind the ESP32 build.

## License

The radio's own code is MIT, like the rest of the board's software. It's built on:

- **Bluepad32** (Apache 2.0) and **BTstack**. BTstack is free for non-commercial use; **a commercial product using
  the ESP32 build needs a BTstack license from [BlueKitchen](https://bluekitchen-gmbh.com)**. The Pico W build is
  covered by Raspberry Pi's BTstack license, which comes with the Pico SDK.
- **ESP-IDF** and Espressif's **mDNS** component (Apache 2.0).
- The display font is Daniel Hepper's **font8x8** (public domain).

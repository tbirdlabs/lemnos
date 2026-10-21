# Salient radio on a Pico W / Pico 2 W (experimental)

The same Bluetooth layer (`../shared/bt.c`) and core (`../core/`) as the ESP32 build, on the Pico SDK. It sends the
SCORPIO the same lines (`HELLO`, `IN`, `CTL`; it answers `HELLO` and `PAIR`), so the SCORPIO can't tell the
difference.

What it does: Bluetooth controllers (Wiimote, Xbox, Xbox Adaptive Controller, other gamepads) in player slots p1 to
p6, remembered across power-off, with pairing mode from the **BOOTSEL** button (press: on for a minute, or off) or
the SCORPIO's `radio pair`. The LED blinks while pairing and stays on while anyone's connected; with nothing paired
yet, pairing mode starts at power-up.

Not yet: WiFi, so no settings page, phone controllers or time. It's allowed to lag behind the ESP32 build.

## Wiring

| Pico W pin | SCORPIO pin |
| --- | --- |
| GP4 (UART1 TX) | RX (GPIO1) |
| GP5 (UART1 RX) | TX (GPIO0) |
| GND | GND |

Power from the board's 5 V into VSYS. Other UART1 pins: `-DRADIO_UART_TX=8 -DRADIO_UART_RX=9` (or 20/21). GP23-25
and GP29 belong to the WiFi chip.

## Building

Needs the Pico SDK 2.1.1 or later (Raspberry Pi's VS Code extension or Windows installer sets it up), and Bluepad32
fetched once with `python ../tools/get_bluepad32.py`.

```
cmake -B build -G Ninja -DPICO_SDK_PATH=/path/to/pico-sdk                      (Pico W)
cmake -B build2 -G Ninja -DPICO_SDK_PATH=/path/to/pico-sdk -DPICO_BOARD=pico2_w  (Pico 2 W)
cmake --build build
```

Hold BOOTSEL while plugging it in and copy `build/salient_radio.uf2` onto the RPI-RP2 (or RP2350) drive. The USB
serial port shows its log.

On Windows without the SDK's tool builds, add `-Dpioasm_DIR=…/pioasm -Dpicotool_DIR=…/picotool` pointing at the
prebuilt `pico-sdk-tools` and `picotool` from https://github.com/raspberrypi/pico-sdk-tools/releases.

## License

BTstack on the Pico W is covered by Raspberry Pi's license for it (it comes with the Pico SDK), so this build needs
no separate BTstack license. `btstack_config.h` is Bluepad32's (Apache 2.0); `pico_sdk_import.cmake` is the Pico
SDK's (BSD 3-clause).

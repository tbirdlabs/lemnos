// Per-board pins. One source tree; platformio.ini picks the board with -DRADIO_BOARD=..., which main/CMakeLists.txt
// turns into RADIO_BOARD_<name>. Only the original ESP32 is supported (BT Classic is needed for the Wiimote).
#pragma once

#if defined(RADIO_BOARD_ttgo_t_display)
// LilyGO TTGO T-Display: GPIO16 is the display's DC line, so the UART moves to GPIO25/26.
#define BOARD_NAME "TTGO T-Display"
#define BOARD_UART_TX 25           // -> SCORPIO RX (GPIO1)
#define BOARD_UART_RX 26           // <- SCORPIO TX (GPIO0)
#define BOARD_BUTTON_A 0           // the two buttons beside the USB socket; either one works (pair / hold: WiFi reset)
#define BOARD_BUTTON_B 35
#define BOARD_DISPLAY 1
#define DISPLAY_MOSI 19
#define DISPLAY_SCLK 18
#define DISPLAY_CS 5
#define DISPLAY_DC 16
#define DISPLAY_RST 23
#define DISPLAY_BL 4
#elif defined(RADIO_BOARD_nodemcu32s)
// NodeMCU-32S (Ai-Thinker ESP-32S): the same GPIOs as the reference board, in a different header order
#define BOARD_NAME "NodeMCU-32S"
#define BOARD_UART_TX 17
#define BOARD_UART_RX 16
#define BOARD_BUTTON_A 0           // BOOT
#define BOARD_BUTTON_B -1
#define BOARD_DISPLAY 0
#else
// Reference: a generic ESP32-WROOM-32 dev board (ESP32 DevKitC and clones)
#define BOARD_NAME "ESP32 DevKit"
#define BOARD_UART_TX 17
#define BOARD_UART_RX 16
#define BOARD_BUTTON_A 0           // BOOT
#define BOARD_BUTTON_B -1
#define BOARD_DISPLAY 0
#endif

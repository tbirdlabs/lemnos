// The radio's shared state and its link to the SCORPIO. Bluetooth (bt.c), the web server (web.c), the clock
// (clock.c), the display and the console all meet here. Everything below is guarded by one lock: hub_lock() /
// hub_unlock() around reads of hub_settings, hub_known, hub_board; the hub_* calls take it themselves.
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "known.h"
#include "link.h"
#include "pads.h"

#define RADIO_FW_VERSION "1.2.0"

typedef struct {
    char tz[48];                       // IANA time zone id (core/tz.h); "" = the default
    int brightness;                    // 1..10, or 0 = not set (the board keeps its own)
    char game[32];                     // a game on the SCORPIO, or "" = not set (it runs its config.GAME)
    char ssid[33];
    char pass[65];
} radio_settings_t;

typedef struct {
    bool seen;                         // the SCORPIO has said HELLO
    char fw[32];                       // its version
    char game[32];                     // the game it's running (STATE game)
    char games[160];                   // the games it has, space-separated (GAMES)
    uint32_t last_ms;                  // when it last sent anything
} board_info_t;

extern radio_settings_t hub_settings;
extern known_table_t hub_known;
extern board_info_t hub_board;

void hub_init(void);                   // loads the saved settings and controllers, opens the UART, starts the hub task
void hub_lock(void);
void hub_unlock(void);
uint32_t hub_ms(void);                 // milliseconds since boot

// Controllers. hub_connect announces it (CTL ... connected) and returns its slot, or 0 if every slot is taken.
int hub_connect(const uint8_t id[6], link_kind_t kind, const char* name);
void hub_disconnect(const uint8_t id[6]);
void hub_input(int slot, const pad_input_t* in);
bool hub_set_slot(const uint8_t id[6], int slot);
bool hub_set_grip(const uint8_t id[6], int grip);   // how a Wiimote is held (GRIP_*, known.h); saved
int hub_forget(const uint8_t id[6]);   // the slot it was playing in, or 0 (bt_forget also drops its pairing)
void hub_fake_action(int slot, link_action_t a);   // console testing: an IN line as if a controller sent it

// Settings: saved, and pushed to the SCORPIO
void hub_set_brightness(int level);
void hub_set_game(const char* game);
void hub_set_tz(const char* id);
void hub_set_wifi(const char* ssid, const char* pass);
const char* hub_tz_rule(void);         // the POSIX rule for the chosen time zone (lock held or not; it's static)

// Lines to the SCORPIO (thread-safe; a line is written whole)
void hub_send(const char* line);
void hub_echo(bool on);                // print every line sent and received on the console

// The web server: the settings page (/), the phone controller (/pad, over a WebSocket at /ws) and the JSON API the
// pages use (/api/...). Served by the radio itself; no internet needed.
#pragma once

#include <stdint.h>

void web_start(void);
void web_tick(uint32_t now);           // the hub task calls it: drops phones that went quiet
void web_slots_changed(void);          // tell each phone page its player slot

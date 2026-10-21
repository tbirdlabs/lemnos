// The board's own buttons (BOOT on a dev board; either button on the T-Display): a press turns pairing mode on (or
// off again); holding one 10 seconds forgets the WiFi network and restarts into setup.
#pragma once

#include <stdint.h>

void buttons_init(void);
void buttons_poll(uint32_t now);       // the hub task calls it every 10 ms

#include "buttons.h"

#include <stdbool.h>

#include "board.h"
#include "bt.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "net.h"

#define DEBOUNCE_MS 30
#define RESET_HOLD_MS 10000

static const char* TAG = "buttons";
static const int PINS[] = {BOARD_BUTTON_A, BOARD_BUTTON_B};

typedef struct {
    bool down;
    bool held;                         // the long hold already acted
    uint32_t since;
} btn_t;

static btn_t btn[2];

void buttons_init(void) {
    for (int i = 0; i < 2; i++) {
        if (PINS[i] < 0)
            continue;
        gpio_reset_pin(PINS[i]);
        gpio_set_direction(PINS[i], GPIO_MODE_INPUT);
        if (PINS[i] < 34)                          // GPIO34-39 have no pull-ups (the T-Display has its own)
            gpio_set_pull_mode(PINS[i], GPIO_PULLUP_ONLY);
    }
}

void buttons_poll(uint32_t now) {
    for (int i = 0; i < 2; i++) {
        if (PINS[i] < 0)
            continue;
        btn_t* b = &btn[i];
        bool down = gpio_get_level(PINS[i]) == 0;
        if (down != b->down && now - b->since >= DEBOUNCE_MS) {
            b->down = down;
            b->since = now;
            if (!down && !b->held)
                bt_pair(bt_pairing_left() == 0);
            b->held = false;
        } else if (b->down && !b->held && now - b->since >= RESET_HOLD_MS) {
            b->held = true;
            ESP_LOGW(TAG, "button held 10 s: forgetting WiFi");
            net_forget_wifi();
        }
    }
}

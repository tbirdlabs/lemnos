#include "hub.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "board.h"
#include "bt.h"
#include "buttons.h"
#include "clock.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "store.h"
#include "tz.h"
#include "web.h"

#define UART UART_NUM_2
#define SAVE_AFTER_MS 500              // settle time before writing flash

static const char* TAG = "hub";

radio_settings_t hub_settings;
known_table_t hub_known;
board_info_t hub_board;

static SemaphoreHandle_t lock;
static pads_t pads;
static bool echo;
static volatile uint32_t known_dirty, settings_dirty;     // when it changed (0 = saved)

uint32_t hub_ms(void) {
    return (uint32_t)(esp_timer_get_time() / 1000);
}

void hub_lock(void) {
    xSemaphoreTakeRecursive(lock, portMAX_DELAY);
}

void hub_unlock(void) {
    xSemaphoreGiveRecursive(lock);
}

void hub_echo(bool on) {
    echo = on;
}

void hub_send(const char* line) {
    uart_write_bytes(UART, line, strlen(line));
    if (echo)
        printf("> %s", line);
}

static void copy(char* dst, const char* src, size_t n) {
    strncpy(dst, src, n - 1);
    dst[n - 1] = 0;
}

// ---- controllers ----

static void send_ctl(int slot) {
    char l[LINK_LINE_MAX + 2];
    int i = hub_known.live[slot];
    link_fmt_ctl(l, slot, i >= 0 ? (link_kind_t)hub_known.k[i].kind : KIND_NONE);
    hub_send(l);
}

static void emit(int slot, link_action_t a, void* ctx) {
    (void)ctx;
    char l[LINK_LINE_MAX + 2];
    link_fmt_in(l, slot, a);
    hub_send(l);
}

static void known_changed(void) {
    known_dirty = hub_ms() | 1;
}

int hub_connect(const uint8_t id[6], link_kind_t kind, const char* name) {
    hub_lock();
    bool was = known_live_slot(&hub_known, id) != 0;
    int slot = known_connect(&hub_known, id, kind, name);
    if (slot && !was) {
        pads_release(&pads, slot);
        send_ctl(slot);
        known_changed();
    }
    hub_unlock();
    if (slot && !was)
        web_slots_changed();
    return slot;
}

void hub_disconnect(const uint8_t id[6]) {
    hub_lock();
    int slot = known_disconnect(&hub_known, id);
    if (slot) {
        pads_release(&pads, slot);
        send_ctl(slot);
    }
    hub_unlock();
    if (slot)
        web_slots_changed();
}

void hub_input(int slot, const pad_input_t* in) {
    hub_lock();
    pads_input(&pads, slot, in, hub_ms());
    hub_unlock();
}

void hub_fake_action(int slot, link_action_t a) {
    hub_lock();
    emit(slot, a, NULL);
    hub_unlock();
}

bool hub_set_slot(const uint8_t id[6], int slot) {
    int ch[2];
    hub_lock();
    bool found = known_find(&hub_known, id) >= 0;
    int n = known_set_slot(&hub_known, id, slot, ch);
    for (int i = 0; i < n; i++) {
        pads_release(&pads, ch[i]);
        send_ctl(ch[i]);
    }
    if (found)
        known_changed();
    hub_unlock();
    web_slots_changed();
    return found;
}

bool hub_set_grip(const uint8_t id[6], int grip) {
    hub_lock();
    bool found = known_set_grip(&hub_known, id, grip);
    if (found) {
        int slot = known_live_slot(&hub_known, id);
        if (slot)
            pads_release(&pads, slot);              // nothing stays held from the old buttons
        known_changed();
    }
    hub_unlock();
    return found;
}

int hub_forget(const uint8_t id[6]) {
    hub_lock();
    int slot = known_forget(&hub_known, id);
    if (slot) {
        pads_release(&pads, slot);
        send_ctl(slot);
    }
    known_changed();
    hub_unlock();
    web_slots_changed();
    return slot;
}

// ---- settings ----

static void settings_changed(void) {
    settings_dirty = hub_ms() | 1;
}

static void send_set(const char* key, const char* value) {
    char l[LINK_LINE_MAX + 2];
    link_fmt_set(l, key, value);
    hub_send(l);
}

// The board keeps its own game and brightness (it saves them, whoever set them: this page or its USB page) and
// tells us with STATE; hub_settings follows it. A change made here goes to it at once, and again at its next HELLO
// until it ACKs, in case it wasn't listening (otherwise a radio that pushed its settings at every HELLO would undo
// a change made on the USB page since).
static bool pending_game, pending_brightness;

static void send_brightness(void) {
    char v[8];
    if (hub_settings.brightness)
        snprintf(v, sizeof(v), "%d", hub_settings.brightness);
    else
        strcpy(v, "default");
    send_set("brightness", v);
}

static void send_game(void) {
    send_set("game", hub_settings.game[0] ? hub_settings.game : "default");
}

// The settings changed here that the board hasn't ACKed yet (lock held)
static void push_settings(void) {
    if (pending_brightness)
        send_brightness();
    if (pending_game)
        send_game();
}

// The board's STATE for a setting: what it runs now, so what this page shows (lock held)
static void board_state(const char* key, const char* value) {
    if (strcmp(key, "game") == 0) {
        copy(hub_board.game, value, sizeof(hub_board.game));
        if (!pending_game && strcmp(hub_settings.game, value) != 0) {
            copy(hub_settings.game, value, sizeof(hub_settings.game));
            settings_changed();
        }
    } else if (strcmp(key, "brightness") == 0) {
        int b = strcmp(value, "default") == 0 ? 0 : atoi(value);
        if (!pending_brightness && b >= 0 && b <= 10 && b != hub_settings.brightness) {
            hub_settings.brightness = b;
            settings_changed();
        }
    } else if (strcmp(key, "fw") == 0) {
        copy(hub_board.fw, value, sizeof(hub_board.fw));
    }
}

void hub_set_brightness(int level) {
    if (level < 0 || level > 10)
        return;
    hub_lock();
    hub_settings.brightness = level;
    pending_brightness = true;
    send_brightness();
    settings_changed();
    hub_unlock();
}

void hub_set_game(const char* game) {
    hub_lock();
    copy(hub_settings.game, game, sizeof(hub_settings.game));
    pending_game = true;
    send_game();
    settings_changed();
    hub_unlock();
}

void hub_set_tz(const char* id) {
    if (tz_find(id) < 0)
        return;
    hub_lock();
    copy(hub_settings.tz, id, sizeof(hub_settings.tz));
    settings_changed();
    hub_unlock();
    clock_send_now();
}

void hub_set_wifi(const char* ssid, const char* pass) {
    hub_lock();
    copy(hub_settings.ssid, ssid, sizeof(hub_settings.ssid));
    copy(hub_settings.pass, pass, sizeof(hub_settings.pass));
    hub_unlock();
    store_save_settings(&hub_settings);             // now: a restart follows
}

const char* hub_tz_rule(void) {
    int i = tz_find(hub_settings.tz);
    if (i < 0)
        i = tz_find(tz_default);
    return tz_zones[i].posix;
}

// ---- the link ----

// Everything the SCORPIO should know, after it (or the radio) starts (lock held)
static void hello(void) {
    char l[LINK_LINE_MAX + 2];
    link_fmt_hello(l, RADIO_FW_VERSION);
    hub_send(l);
    push_settings();
    for (int s = 1; s <= KNOWN_SLOTS; s++)
        if (hub_known.live[s] >= 0)
            send_ctl(s);
}

static void handle(char* line) {
    if (echo)
        printf("< %s\n", line);
    hub_lock();
    hub_board.last_ms = hub_ms();
    link_msg_t m = link_parse(line);
    bool pair = false, pair_on = false, time_now = false;
    switch (m.type) {
        case MSG_HELLO:
            hub_board.seen = true;
            copy(hub_board.fw, m.key, sizeof(hub_board.fw));
            hello();
            time_now = true;
            break;
        case MSG_STATE:
            board_state(m.key, m.value);
            break;
        case MSG_GAMES:
            copy(hub_board.games, m.key, sizeof(hub_board.games));
            break;
        case MSG_PAIR:
            pair = true;
            pair_on = strcmp(m.key, "on") == 0;
            break;
        case MSG_ACK:
            if (strcmp(m.key, "game") == 0)
                pending_game = false;
            else if (strcmp(m.key, "brightness") == 0)
                pending_brightness = false;
            break;
        case MSG_UNKNOWN:
            break;
    }
    if (!hub_board.seen && m.type != MSG_UNKNOWN) {
        // The board is running but hasn't said HELLO: it was running before this radio started, so it answered
        // (or missed) the HELLO we sent at start. Say it again: the board answers with its version, game and games;
        // the settings and controllers go along, and the time.
        hub_board.seen = true;
        hello();
        time_now = true;
    }
    hub_unlock();
    if (pair)
        bt_pair(pair_on);
    if (time_now)
        clock_send_now();
}

static void save_if_due(uint32_t now) {
    if (settings_dirty && now - settings_dirty >= SAVE_AFTER_MS) {
        static radio_settings_t s;
        settings_dirty = 0;
        hub_lock();
        s = hub_settings;
        hub_unlock();
        store_save_settings(&s);
    }
    if (known_dirty && now - known_dirty >= SAVE_AFTER_MS) {
        static known_table_t k;
        known_dirty = 0;
        hub_lock();
        k = hub_known;
        hub_unlock();
        store_save_known(&k);
    }
}

static void hub_task(void* arg) {
    (void)arg;
    static link_rx_t rx;
    uint8_t buf[128];
    link_rx_init(&rx);
    for (;;) {
        int n = uart_read_bytes(UART, buf, sizeof(buf), pdMS_TO_TICKS(10));
        for (int i = 0; i < n; i++) {
            char* line = link_rx_byte(&rx, (char)buf[i]);
            if (line)
                handle(line);
        }
        uint32_t now = hub_ms();
        hub_lock();
        pads_tick(&pads, now);
        hub_unlock();
        buttons_poll(now);
        web_tick(now);
        save_if_due(now);
    }
}

void hub_init(void) {
    lock = xSemaphoreCreateRecursiveMutex();
    pads_init(&pads, emit, NULL);
    store_load(&hub_settings, &hub_known);
    if (tz_find(hub_settings.tz) < 0)
        copy(hub_settings.tz, tz_default, sizeof(hub_settings.tz));

    const uart_config_t cfg = {
        .baud_rate = 115200,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(UART, 1024, 2048, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(UART, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(UART, BOARD_UART_TX, BOARD_UART_RX, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    // the SCORPIO's TX idles high; with no board on the other end, keep RX from floating into noise
    gpio_set_pull_mode(BOARD_UART_RX, GPIO_PULLUP_ONLY);
    buttons_init();
    ESP_LOGI(TAG, "UART to the SCORPIO: TX GPIO%d, RX GPIO%d, 115200 8N1", BOARD_UART_TX, BOARD_UART_RX);

    hub_lock();
    hub_send("\n");                                  // ends any garbage our TX pin made while the ESP32 started
    hello();                                         // in case the SCORPIO is already running
    hub_unlock();
    xTaskCreatePinnedToCore(hub_task, "hub", 3072, NULL, 5, NULL, 1);
}

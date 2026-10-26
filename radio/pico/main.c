// The Lemnos radio on a Pico W / Pico 2 W (experimental): Bluetooth controllers (shared/bt.c, Bluepad32) sent to
// the SCORPIO as IN / CTL lines over UART1 (GP4 TX, GP5 RX by default), the same protocol as the ESP32 build
// (core/link.h, docs/protocol.md). No WiFi yet: no settings page, phones or time.
//
// Everything runs on BTstack's run loop, so the hub here needs no locks: a 10 ms timer reads the UART, repeats held
// directions, watches the BOOTSEL button (a press toggles pairing mode) and drives the LED (blinking while pairing,
// on while anyone's connected). The controllers the radio knows are kept in BTstack's flash store, beside the
// pairing keys.

#include <stdio.h>
#include <string.h>

#include <btstack.h>
#include <btstack_run_loop.h>
#include <btstack_tlv.h>
#include <pico/cyw43_arch.h>
#include <pico/stdlib.h>
#include <uni.h>

#include "bt.h"
#include "hardware/gpio.h"
#include "hardware/structs/ioqspi.h"
#include "hardware/structs/sio.h"
#include "hardware/sync.h"
#include "hardware/uart.h"
#include "hub.h"
#include "sdkconfig.h"

#ifndef CONFIG_BLUEPAD32_PLATFORM_CUSTOM
#error "Needs CONFIG_BLUEPAD32_PLATFORM_CUSTOM (sdkconfig.h)"
#endif

#define UART uart1
#define TICK_MS 10
#define BUTTON_EVERY_MS 50
#define SAVE_AFTER_MS 500
#define TAG_KNOWN (('S' << 24) | ('L' << 16) | ('K' << 8) | 'N')     // BTstack TLV tag for the known controllers
#define VERSION RADIO_FW_VERSION "-picow"

radio_settings_t hub_settings;         // (the ESP32's; nothing to set without WiFi)
known_table_t hub_known;
board_info_t hub_board;

static pads_t pads;
static link_rx_t rx;
static uint32_t known_dirty;
static btstack_timer_source_t tick;

// ---- the hub (hub.h), single-threaded ----

void hub_lock(void) {}
void hub_unlock(void) {}

uint32_t hub_ms(void) {
    return to_ms_since_boot(get_absolute_time());
}

void hub_send(const char* line) {
    uart_puts(UART, line);
}

void hub_echo(bool on) {
    (void)on;
}

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

int hub_connect(const uint8_t id[6], link_kind_t kind, const char* name) {
    bool was = known_live_slot(&hub_known, id) != 0;
    int slot = known_connect(&hub_known, id, kind, name);
    if (slot && !was) {
        pads_release(&pads, slot);
        send_ctl(slot);
        known_dirty = hub_ms() | 1;
    }
    return slot;
}

void hub_disconnect(const uint8_t id[6]) {
    int slot = known_disconnect(&hub_known, id);
    if (slot) {
        pads_release(&pads, slot);
        send_ctl(slot);
    }
}

void hub_input(int slot, const pad_input_t* in) {
    pads_input(&pads, slot, in, hub_ms());
}

int hub_forget(const uint8_t id[6]) {
    int slot = known_forget(&hub_known, id);
    if (slot) {
        pads_release(&pads, slot);
        send_ctl(slot);
    }
    known_dirty = hub_ms() | 1;
    return slot;
}

static void load_known(void) {
    const btstack_tlv_t* tlv = NULL;
    void* ctx = NULL;
    static uint8_t blob[KNOWN_BLOB_MAX];
    btstack_tlv_get_instance(&tlv, &ctx);
    int n = tlv ? tlv->get_tag(ctx, TAG_KNOWN, blob, sizeof(blob)) : 0;
    if (n <= 0 || !known_load(&hub_known, blob, (size_t)n))
        known_init(&hub_known);
}

static void save_known(void) {
    const btstack_tlv_t* tlv = NULL;
    void* ctx = NULL;
    static uint8_t blob[KNOWN_BLOB_MAX];
    btstack_tlv_get_instance(&tlv, &ctx);
    if (tlv)
        tlv->store_tag(ctx, TAG_KNOWN, blob, (uint32_t)known_save(&hub_known, blob, sizeof(blob)));
}

// ---- the link ----

static void hello(void) {
    char l[LINK_LINE_MAX + 2];
    link_fmt_hello(l, VERSION);
    hub_send(l);
    for (int s = 1; s <= KNOWN_SLOTS; s++)
        if (hub_known.live[s] >= 0)
            send_ctl(s);
}

static void copy(char* dst, const char* src, size_t n) {
    strncpy(dst, src, n - 1);
    dst[n - 1] = 0;
}

static void handle(char* line) {
    hub_board.last_ms = hub_ms();
    link_msg_t m = link_parse(line);
    switch (m.type) {
        case MSG_HELLO:
            hub_board.seen = true;
            copy(hub_board.fw, m.key, sizeof(hub_board.fw));
            hello();
            break;
        case MSG_STATE:
            if (strcmp(m.key, "game") == 0)
                copy(hub_board.game, m.value, sizeof(hub_board.game));
            break;
        case MSG_GAMES:
            copy(hub_board.games, m.key, sizeof(hub_board.games));
            break;
        case MSG_PAIR:
            bt_pair(strcmp(m.key, "on") == 0);
            break;
        default:
            break;
    }
}

// ---- BOOTSEL and the LED ----

// BOOTSEL is the flash chip's select line: read it by letting the line float for a moment (pico-examples'
// picoboard/button). Runs from RAM with interrupts off, since flash can't be read meanwhile.
static bool __no_inline_not_in_flash_func(bootsel_down)(void) {
    const uint CS = 1;
    uint32_t flags = save_and_disable_interrupts();
    hw_write_masked(&ioqspi_hw->io[CS].ctrl, GPIO_OVERRIDE_LOW << IO_QSPI_GPIO_QSPI_SS_CTRL_OEOVER_LSB,
                    IO_QSPI_GPIO_QSPI_SS_CTRL_OEOVER_BITS);
    for (volatile int i = 0; i < 1000; ++i)
        ;
#if PICO_RP2040
    bool down = !(sio_hw->gpio_hi_in & (1u << CS));
#else
    bool down = !(sio_hw->gpio_hi_in & SIO_GPIO_HI_IN_QSPI_CSN_BITS);
#endif
    hw_write_masked(&ioqspi_hw->io[CS].ctrl, GPIO_OVERRIDE_NORMAL << IO_QSPI_GPIO_QSPI_SS_CTRL_OEOVER_LSB,
                    IO_QSPI_GPIO_QSPI_SS_CTRL_OEOVER_BITS);
    restore_interrupts(flags);
    return down;
}

static void poll_button(uint32_t now) {
    static uint32_t next;
    static bool was;
    if ((int32_t)(now - next) < 0)
        return;
    next = now + BUTTON_EVERY_MS;
    bool down = bootsel_down();
    if (down && !was)
        bt_pair(bt_pairing_left() == 0);
    was = down;
}

static void show_led(uint32_t now) {
    static int lit = -1;
    bool any = false;
    for (int s = 1; s <= KNOWN_SLOTS; s++)
        if (hub_known.live[s] >= 0)
            any = true;
    int on = bt_pairing_left() ? (int)(now / 250 % 2) : any;
    if (on != lit) {
        lit = on;
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, on);
    }
}

static void on_tick(btstack_timer_source_t* t) {
    while (uart_is_readable(UART)) {
        char* line = link_rx_byte(&rx, (char)uart_getc(UART));
        if (line)
            handle(line);
    }
    uint32_t now = hub_ms();
    pads_tick(&pads, now);
    poll_button(now);
    show_led(now);
    if (known_dirty && now - known_dirty >= SAVE_AFTER_MS) {
        known_dirty = 0;
        save_known();
    }
    btstack_run_loop_set_timer(t, TICK_MS);
    btstack_run_loop_add_timer(t);
}

int main(void) {
    stdio_init_all();
    uart_init(UART, 115200);
    gpio_set_function(RADIO_UART_TX, GPIO_FUNC_UART);
    gpio_set_function(RADIO_UART_RX, GPIO_FUNC_UART);
    gpio_pull_up(RADIO_UART_RX);                       // no SCORPIO on the other end: no noise either

    if (cyw43_arch_init()) {                           // the CYW43 (and with it BTstack and its flash store)
        printf("cyw43_arch_init failed\n");
        return -1;
    }
    load_known();
    pads_init(&pads, emit, NULL);
    link_rx_init(&rx);
    hello();

    uni_platform_set_custom(bt_platform());
    uni_init(0, NULL);

    btstack_run_loop_set_timer_handler(&tick, on_tick);
    btstack_run_loop_set_timer(&tick, TICK_MS);
    btstack_run_loop_add_timer(&tick);
    btstack_run_loop_execute();                        // doesn't return
    return 0;
}

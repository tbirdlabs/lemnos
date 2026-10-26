// Bluetooth controllers (Bluepad32 custom platform), for every build (ESP32 and Pico W). Runs on BTstack's
// thread; the platform's hub (hub.h) does the rest.
//
// Who may connect: controllers the radio knows (hub_known), and, while pairing mode is on, anything that's a gamepad.
//   - BLE controllers (Xbox, XAC) reconnect by advertising, so BLE scanning stays on; on_device_discovered turns
//     away the ones it doesn't know unless pairing.
//   - Classic controllers (Wiimote) reconnect by calling in: Bluepad32's allowlist (kept equal to the known
//     Classic controllers) turns away strangers; pairing switches it off.
//   - Classic inquiry (finding a Wiimote in sync mode) runs only while pairing: it's heavy on the radio, which the
//     WiFi shares.
//   - BLE scanning is part-time: Bluepad32 scans all the time (a 30 ms window every 30 ms), which on the ESP32 leaves
//     WiFi too little airtime to answer even DHCP. Known controllers reconnect by advertising many times a second,
//     so a short window finds them; pairing mode scans half the time for its minute.
// Buttons: everything becomes a pad_input (core/pads.h); pads.c adds the deadzone and auto-repeat.
//   Wiimote, as each one is set to be held (its grip, on the web page):
//     upright (the default; one hand): D-pad moves, A = pick, B (the trigger underneath) = back
//     sideways (two hands, D-pad on the left): D-pad moves, 2 = pick, 1 = back
//     either way, Home = menu (the board's game picker)
//     A Nunchuk's stick moves too, held either way.
//   Xbox, Xbox Adaptive Controller, other gamepads: D-pad or left stick moves, A = pick, B = back, the Xbox (or
//   PS, Home) button or Start = menu.

#include "bt.h"

#include <string.h>

#include <btstack.h>
#include <uni.h>

#include "hub.h"
#include "port.h"

static const char* TAG = "bt";

// BLE scan timing, in 0.625 ms units: (interval, window)
#define SCAN_IDLE_INTERVAL 96              // 60 ms
#define SCAN_IDLE_WINDOW 16                // 10 ms: a sixth of the time
#define SCAN_PAIR_INTERVAL 48              // 30 ms
#define SCAN_PAIR_WINDOW 24                // 15 ms: half

static bool pairing;
static volatile uint32_t pair_until;              // hub_ms() when pairing ends, 0 = off
static btstack_timer_source_t pair_timer;

typedef struct {
    uint8_t slot;                                  // the player slot it's playing in, 0 = not accepted (yet)
} bt_dev_t;

static bt_dev_t* dev(uni_hid_device_t* d) {
    return (bt_dev_t*)&d->platform_data[0];
}

static link_kind_t kind_of(const uni_hid_device_t* d) {
    if (d->controller_type == CONTROLLER_TYPE_WiiController)
        return KIND_WIIMOTE;
    if (d->vendor_id == 0x045e && (d->product_id == 0x0b0a || d->product_id == 0x0b0c || d->product_id == 0x0b21))
        return KIND_XAC;
    if (strstr(d->name, "Adaptive"))
        return KIND_XAC;
    if (d->controller_type == CONTROLLER_TYPE_XBoxOneController)
        return KIND_XBOX;
    return KIND_GAMEPAD;
}

static bool is_known(const uint8_t* addr) {
    hub_lock();
    bool k = known_find(&hub_known, addr) >= 0;
    hub_unlock();
    return k;
}

// ---- pairing mode ----

static void pair_set(bool on);

static void pair_timeout(btstack_timer_source_t* t) {
    (void)t;
    LOGI(TAG, "pairing mode timed out");
    pair_set(false);
}

static void pair_set(bool on) {
    btstack_run_loop_remove_timer(&pair_timer);
    pairing = on;
    if (on) {
        pair_until = hub_ms() + BT_PAIR_SECONDS * 1000;
        uni_bt_allowlist_set_enabled(false);
        gap_set_scan_parameters(0, SCAN_PAIR_INTERVAL, SCAN_PAIR_WINDOW);
        uni_bt_bredr_scan_start();
        btstack_run_loop_set_timer_handler(&pair_timer, pair_timeout);
        btstack_run_loop_set_timer(&pair_timer, BT_PAIR_SECONDS * 1000);
        btstack_run_loop_add_timer(&pair_timer);
        LOGI(TAG, "pairing mode on for %d s", BT_PAIR_SECONDS);
    } else {
        pair_until = 0;
        uni_bt_bredr_scan_stop();
        gap_set_scan_parameters(0, SCAN_IDLE_INTERVAL, SCAN_IDLE_WINDOW);
        uni_bt_allowlist_set_enabled(true);
        LOGI(TAG, "pairing mode off");
    }
}

int bt_pairing_left(void) {
    uint32_t until = pair_until;
    if (!until)
        return 0;
    int32_t left = (int32_t)(until - hub_ms());
    return left > 0 ? (left + 999) / 1000 : 0;
}

// The allowlist holds the known Classic controllers (and BLE ones: harmless, it's only checked for Classic)
static void sync_allowlist(void) {
    const bd_addr_t* list;
    int total;
    bd_addr_t had[CONFIG_BLUEPAD32_MAX_ALLOWLIST];
    uni_bt_allowlist_get_all(&list, &total);
    if (total > CONFIG_BLUEPAD32_MAX_ALLOWLIST)
        total = CONFIG_BLUEPAD32_MAX_ALLOWLIST;
    memcpy(had, list, sizeof(bd_addr_t) * total);
    static const bd_addr_t zero = {0};
    hub_lock();
    for (int i = 0; i < total; i++)
        if (memcmp(had[i], zero, 6) && known_find(&hub_known, had[i]) < 0)
            uni_bt_allowlist_remove_addr(had[i]);
    for (int i = 0; i < KNOWN_MAX; i++) {
        known_t* e = &hub_known.k[i];
        if (e->used && e->kind != KIND_PHONE)
            uni_bt_allowlist_add_addr(e->id);       // (it skips ones already there)
    }
    hub_unlock();
}

static bool knows_a_bt_controller(void) {
    bool any = false;
    hub_lock();
    for (int i = 0; i < KNOWN_MAX; i++)
        if (hub_known.k[i].used && hub_known.k[i].kind != KIND_PHONE)
            any = true;
    hub_unlock();
    return any;
}

// ---- jobs posted from other tasks onto BTstack's thread ----

enum { JOB_PAIR_ON = 1, JOB_PAIR_OFF, JOB_FORGET };

typedef struct {
    btstack_context_callback_registration_t reg;
    int what;
    uint8_t id[6];
} job_t;

static job_t jobs[8];
static int next_job;
static port_mux_t jobs_mux = PORT_MUX_INIT;

static void forget_now(const uint8_t* id) {
    bd_addr_t a;
    memcpy(a, id, 6);
    uni_hid_device_t* d = uni_hid_device_get_instance_for_address(a);
    if (d) {
        uni_hid_device_disconnect(d);
        uni_hid_device_delete(d);
    }
    gap_drop_link_key_for_bd_addr(a);
    for (int i = 0; i < le_device_db_max_count(); i++) {
        int type;
        bd_addr_t e;
        le_device_db_info(i, &type, e, NULL);
        if (type != BD_ADDR_TYPE_UNKNOWN && memcmp(e, a, 6) == 0)
            le_device_db_remove(i);
    }
    uni_bt_allowlist_remove_addr(a);
    hub_forget(id);
    LOGI(TAG, "forgot %s", bd_addr_to_str(a));
}

static void run_job(void* ctx) {
    job_t* j = ctx;
    switch (j->what) {
        case JOB_PAIR_ON:
            pair_set(true);
            break;
        case JOB_PAIR_OFF:
            pair_set(false);
            break;
        case JOB_FORGET:
            forget_now(j->id);
            break;
    }
}

static void post(int what, const uint8_t* id) {
    port_enter(&jobs_mux);
    job_t* j = &jobs[next_job];
    next_job = (next_job + 1) % 8;
    port_exit(&jobs_mux);
    j->what = what;
    if (id)
        memcpy(j->id, id, 6);
    j->reg.callback = run_job;
    j->reg.context = j;
    btstack_run_loop_execute_on_main_thread(&j->reg);
}

void bt_pair(bool on) {
    post(on ? JOB_PAIR_ON : JOB_PAIR_OFF, NULL);
}

void bt_forget(const uint8_t id[6]) {
    post(JOB_FORGET, id);
}

// ---- Bluepad32 callbacks ----

static void on_init(int argc, const char** argv) {
    (void)argc;
    (void)argv;
}

static void on_init_complete(void) {
    // BLE scanning (for reconnects), part-time. Classic inquiry only runs while pairing, so it isn't started here:
    // Bluepad32's own start (uni_bt_start_scanning_and_autoconnect) starts both, and an inquiry stop sent before the
    // start has completed is lost, leaving inquiry running and WiFi starved.
    gap_set_scan_parameters(0, SCAN_IDLE_INTERVAL, SCAN_IDLE_WINDOW);
    uni_bt_le_scan_start();
    uni_bt_allow_incoming_connections(true);
    sync_allowlist();
    uni_bt_allowlist_set_enabled(true);
    if (!knows_a_bt_controller()) {
        LOGI(TAG, "no controllers paired yet");
        pair_set(true);
    }
}

static uni_error_t on_device_discovered(bd_addr_t addr, const char* name, uint16_t cod, uint8_t rssi) {
    (void)rssi;
    if (((cod & UNI_BT_COD_MINOR_MASK) & UNI_BT_COD_MINOR_KEYBOARD) == UNI_BT_COD_MINOR_KEYBOARD)
        return UNI_ERROR_IGNORE_DEVICE;
    if (pairing || is_known(addr))
        return UNI_ERROR_SUCCESS;
    return UNI_ERROR_IGNORE_DEVICE;
}

static void on_device_connected(uni_hid_device_t* d) {
    dev(d)->slot = 0;
}

static void greet(uni_hid_device_t* d, int slot) {
    if (d->report_parser.set_player_leds)
        d->report_parser.set_player_leds(d, slot <= 4 ? 1 << (slot - 1) : (slot == 5 ? 0x9 : 0x6));
    if (d->report_parser.play_dual_rumble)
        d->report_parser.play_dual_rumble(d, 0, 150, 128, 40);
}

static uni_error_t on_device_ready(uni_hid_device_t* d) {
    bd_addr_t addr;
    uni_bt_conn_get_address(&d->conn, addr);
    bool known = is_known(addr);
    if (!known && !pairing) {
        LOGI(TAG, "%s: not paired and not pairing, turned away", bd_addr_to_str(addr));
        return UNI_ERROR_IGNORE_DEVICE;
    }
    if (d->parent)
        return UNI_ERROR_IGNORE_DEVICE;                // a virtual device (a DualShock 4's touchpad mouse)
    link_kind_t kind = kind_of(d);
    int slot = hub_connect(addr, kind, d->name);
    if (!slot) {
        LOGW(TAG, "%s: every player slot is taken", bd_addr_to_str(addr));
        return UNI_ERROR_IGNORE_DEVICE;
    }
    dev(d)->slot = (uint8_t)slot;
    if (!known)
        uni_bt_allowlist_add_addr(addr);
    LOGI(TAG, "%s %s (%s) is player %d", known ? "back:" : "paired:", d->name, link_kind_name(kind), slot);
    greet(d, slot);
    return UNI_ERROR_SUCCESS;
}

static void on_device_disconnected(uni_hid_device_t* d) {
    if (!dev(d)->slot)
        return;
    bd_addr_t addr;
    uni_bt_conn_get_address(&d->conn, addr);
    LOGI(TAG, "player %d left (%s)", dev(d)->slot, bd_addr_to_str(addr));
    dev(d)->slot = 0;
    hub_disconnect(addr);
}

// A Wiimote's report as its physical buttons. Bluepad32 turns the D-pad and renames the buttons by the mode it
// picked at connection (a Wiimote alone: sideways; + held while connecting: upright; A held: sideways with the
// accelerometer; a Nunchuk plugged in: upright, its stick in the right-hand axes); this undoes that.
enum { WII_UP = 1, WII_DOWN = 2, WII_LEFT = 4, WII_RIGHT = 8 };        // as seen held upright, pointing away

static void wii_input(const uni_hid_device_t* d, const uni_gamepad_t* gp, int slot, pad_input_t* in) {
    uint8_t dirs = 0;
    bool a, b, one, two;
    switch (d->controller_subtype) {
        case CONTROLLER_SUBTYPE_WIIMOTE_VERTICAL:
        case CONTROLLER_SUBTYPE_WIIMOTE_NUNCHUK:
        case CONTROLLER_SUBTYPE_WIIMOTE_NUNCHUK_ACCEL: {
            bool nunchuk = d->controller_subtype != CONTROLLER_SUBTYPE_WIIMOTE_VERTICAL;
            dirs = (gp->dpad & DPAD_UP ? WII_UP : 0) | (gp->dpad & DPAD_DOWN ? WII_DOWN : 0) |
                   (gp->dpad & DPAD_LEFT ? WII_LEFT : 0) | (gp->dpad & DPAD_RIGHT ? WII_RIGHT : 0);
            a = gp->buttons & BUTTON_B;
            b = gp->buttons & BUTTON_A;
            one = gp->buttons & (nunchuk ? BUTTON_SHOULDER_L : BUTTON_X);
            two = gp->buttons & (nunchuk ? BUTTON_SHOULDER_R : BUTTON_Y);
            if (nunchuk) {
                in->has_stick = true;
                in->sx = (int16_t)gp->axis_rx;
                in->sy = (int16_t)gp->axis_ry;
            }
            break;
        }
        default:                                    // sideways, with or without the accelerometer
            dirs = (gp->dpad & DPAD_LEFT ? WII_UP : 0) | (gp->dpad & DPAD_RIGHT ? WII_DOWN : 0) |
                   (gp->dpad & DPAD_DOWN ? WII_LEFT : 0) | (gp->dpad & DPAD_UP ? WII_RIGHT : 0);
            a = gp->buttons & BUTTON_X;
            b = gp->buttons & BUTTON_Y;
            one = gp->buttons & BUTTON_A;
            two = gp->buttons & BUTTON_B;
            break;
    }
    in->menu = gp->misc_buttons & MISC_BUTTON_SYSTEM;     // Home
    hub_lock();
    int i = hub_known.live[slot];
    int grip = i >= 0 ? hub_known.k[i].grip : GRIP_UPRIGHT;
    hub_unlock();
    if (grip == GRIP_SIDEWAYS) {                    // the D-pad's up points left
        in->dirs = (dirs & WII_RIGHT ? DIR_UP : 0) | (dirs & WII_LEFT ? DIR_DOWN : 0) |
                   (dirs & WII_UP ? DIR_LEFT : 0) | (dirs & WII_DOWN ? DIR_RIGHT : 0);
        in->pick = two;
        in->back = one;
    } else {
        in->dirs = (dirs & WII_UP ? DIR_UP : 0) | (dirs & WII_DOWN ? DIR_DOWN : 0) |
                   (dirs & WII_LEFT ? DIR_LEFT : 0) | (dirs & WII_RIGHT ? DIR_RIGHT : 0);
        in->pick = a;
        in->back = b;
    }
}

static void on_controller_data(uni_hid_device_t* d, uni_controller_t* ctl) {
    int slot = dev(d)->slot;
    if (!slot || ctl->klass != UNI_CONTROLLER_CLASS_GAMEPAD)
        return;
    const uni_gamepad_t* gp = &ctl->gamepad;
    pad_input_t in = {0};
    in.dirs = (gp->dpad & DPAD_UP ? DIR_UP : 0) | (gp->dpad & DPAD_DOWN ? DIR_DOWN : 0) |
              (gp->dpad & DPAD_LEFT ? DIR_LEFT : 0) | (gp->dpad & DPAD_RIGHT ? DIR_RIGHT : 0);
    if (d->controller_type == CONTROLLER_TYPE_WiiController) {
        wii_input(d, gp, slot, &in);
    } else {
        in.pick = gp->buttons & BUTTON_A;
        in.back = gp->buttons & BUTTON_B;
        in.menu = gp->misc_buttons & (MISC_BUTTON_SYSTEM | MISC_BUTTON_START);
        in.has_stick = true;
    }
    if (in.has_stick && d->controller_type != CONTROLLER_TYPE_WiiController) {
        in.sx = (int16_t)gp->axis_x;
        in.sy = (int16_t)gp->axis_y;
    }
    hub_input(slot, &in);
}

static const uni_property_t* get_property(uni_property_idx_t idx) {
    (void)idx;
    return NULL;
}

static void on_oob_event(uni_platform_oob_event_t event, void* data) {
    (void)event;
    (void)data;
}

struct uni_platform* bt_platform(void) {
    static struct uni_platform plat = {
        .name = "lemnos",
        .init = on_init,
        .on_init_complete = on_init_complete,
        .on_device_discovered = on_device_discovered,
        .on_device_connected = on_device_connected,
        .on_device_disconnected = on_device_disconnected,
        .on_device_ready = on_device_ready,
        .on_oob_event = on_oob_event,
        .on_controller_data = on_controller_data,
        .get_property = get_property,
    };
    return &plat;
}

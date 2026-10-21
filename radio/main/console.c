// Console commands for testing, on the USB serial port (115200), alongside Bluepad32's own ("help" lists all):
//   status                         settings, network, time, controllers, the SCORPIO link
//   link on|off                    print every line to and from the SCORPIO
//   pair [on|off]                  pairing mode
//   faketime 2026-11-01T06:59:30Z  set the clock to this UTC time and stop NTP (to watch a DST change)
//   ntp                            back to NTP time
//   fakepad <slot> connect <kind> | disconnect (and forget) | up|down|left|right|pick|back
//                                  act as a controller in a slot, to test the SCORPIO side without one
//   forget <id> | all              forget a controller (or all), dropping its Bluetooth pairing
//   wifi <ssid> [password]         join a network (restarts)
//   wifi_forget                    forget the network (restarts into setup)

#include "console.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "board.h"
#include "bt.h"
#include "clock.h"
#include "esp_console.h"
#include "esp_heap_caps.h"
#include "hub.h"
#include "net.h"
#include "tz.h"

static int cmd_status(int argc, char** argv) {
    (void)argc;
    (void)argv;
    net_status_t ns;
    net_status(&ns);
    int64_t local;
    bool dst;
    printf("Salient radio %s on %s, up %lu s\n", RADIO_FW_VERSION, BOARD_NAME, (unsigned long)(hub_ms() / 1000));
    printf("WiFi: %s%s%s%s\n", ns.connected ? "on " : ns.ssid[0] ? "trying " : "no network saved",
           ns.ssid, ns.connected ? ", " : "", ns.ip);
    if (ns.ap_on)
        printf("Setup network open: %s\n", ns.ap_ssid);
    if (clock_local(&local, &dst)) {
        int y, mo, d, h, mi, s;
        tz_civil(local, &y, &mo, &d, &h, &mi, &s);
        printf("Time (%s): %04d-%02d-%02d %02d:%02d:%02d%s\n", clock_source(), y, mo, d, h, mi, s, dst ? " DST" : "");
    } else {
        printf("Time: not set yet\n");
    }
    printf("Memory: %u bytes free, lowest %u, largest block %u\n", (unsigned)heap_caps_get_free_size(MALLOC_CAP_8BIT),
           (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_8BIT),
           (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_8BIT));
    printf("Pairing: %d s left\n", bt_pairing_left());
    hub_lock();
    printf("Settings: zone %s, brightness %d, game \"%s\"\n", hub_settings.tz, hub_settings.brightness,
           hub_settings.game);
    printf("SCORPIO: %s fw \"%s\", game \"%s\", games \"%s\"\n", hub_board.seen ? "seen," : "not seen yet,",
           hub_board.fw, hub_board.game, hub_board.games);
    for (int i = 0; i < KNOWN_MAX; i++) {
        known_t* e = &hub_known.k[i];
        if (!e->used)
            continue;
        char id[18];
        known_id_str(e->id, id);
        printf("  p%d %-8s %s %s \"%s\"\n", e->slot, link_kind_name(e->kind), id,
               known_is_live(&hub_known, i) ? "connected" : "away", e->name);
    }
    hub_unlock();
    return 0;
}

static int cmd_link(int argc, char** argv) {
    hub_echo(argc < 2 || strcmp(argv[1], "off") != 0);
    return 0;
}

static int cmd_pair(int argc, char** argv) {
    bt_pair(argc < 2 || strcmp(argv[1], "off") != 0);
    return 0;
}

static int cmd_faketime(int argc, char** argv) {
    int y, mo, d, h, mi, s = 0;
    if (argc < 2 || sscanf(argv[1], "%d-%d-%dT%d:%d:%d", &y, &mo, &d, &h, &mi, &s) < 5) {
        printf("faketime 2026-11-01T06:59:30Z   (UTC)\n");
        return 1;
    }
    clock_fake(tz_days(y, mo, d) * 86400 + h * 3600 + mi * 60 + s);
    return 0;
}

static int cmd_ntp(int argc, char** argv) {
    (void)argc;
    (void)argv;
    clock_ntp();
    return 0;
}

static link_kind_t kind_named(const char* s) {
    for (int k = KIND_WIIMOTE; k <= KIND_GAMEPAD; k++)
        if (strcmp(s, link_kind_name(k)) == 0)
            return k;
    return KIND_GAMEPAD;
}

static int cmd_fakepad(int argc, char** argv) {
    int slot = argc >= 3 ? atoi(argv[1]) : 0;
    if (slot < 1 || slot > KNOWN_SLOTS) {
        printf("fakepad <slot 1-6> connect <wiimote|xbox|xac|phone|gamepad> | disconnect | up|down|left|right|pick|back\n");
        return 1;
    }
    uint8_t id[6] = {0xfa, 0xce, 0, 0, 0, (uint8_t)slot};       // a made-up controller per slot
    const char* what = argv[2];
    if (strcmp(what, "connect") == 0) {
        if (hub_connect(id, kind_named(argc >= 4 ? argv[3] : "gamepad"), "Console") != slot)
            hub_set_slot(id, slot);                             // it landed elsewhere: move it (swapping if taken)
        return 0;
    }
    if (strcmp(what, "disconnect") == 0) {
        hub_forget(id);                                         // (a made-up controller isn't worth remembering)
        return 0;
    }
    for (int a = ACT_UP; a <= ACT_BACK; a++)
        if (strcmp(what, link_action_name(a)) == 0) {
            hub_fake_action(slot, a);
            return 0;
        }
    printf("unknown: %s\n", what);
    return 1;
}

static int cmd_forget(int argc, char** argv) {
    uint8_t id[6];
    if (argc >= 2 && strcmp(argv[1], "all") == 0) {
        uint8_t ids[KNOWN_MAX][6];
        uint8_t kinds[KNOWN_MAX];
        int n = 0;
        hub_lock();
        for (int i = 0; i < KNOWN_MAX; i++)
            if (hub_known.k[i].used) {
                memcpy(ids[n], hub_known.k[i].id, 6);
                kinds[n++] = hub_known.k[i].kind;
            }
        hub_unlock();
        for (int i = 0; i < n; i++) {
            if (kinds[i] == KIND_PHONE || ids[i][0] == 0xfa)    // phones and fakepads have no pairing to drop
                hub_forget(ids[i]);
            else
                bt_forget(ids[i]);
        }
        printf("forgot %d\n", n);
        return 0;
    }
    if (argc < 2 || !known_id_parse(argv[1], id)) {
        printf("forget <id as status shows it> | all\n");
        return 1;
    }
    bt_forget(id);
    return 0;
}

static int cmd_wifi(int argc, char** argv) {
    if (argc < 2) {
        printf("wifi <ssid> [password]\n");
        return 1;
    }
    hub_set_wifi(argv[1], argc >= 3 ? argv[2] : "");
    net_restart_soon();
    return 0;
}

static int cmd_wifi_forget(int argc, char** argv) {
    (void)argc;
    (void)argv;
    net_forget_wifi();
    return 0;
}

void console_start(void) {
    const esp_console_cmd_t cmds[] = {
        {.command = "status", .help = "Salient: settings, network, time, controllers, link", .func = cmd_status},
        {.command = "link", .help = "Salient: link on|off prints the lines to and from the SCORPIO", .func = cmd_link},
        {.command = "pair", .help = "Salient: pair [on|off]", .func = cmd_pair},
        {.command = "faketime", .help = "Salient: faketime 2026-11-01T06:59:30Z (UTC; stops NTP)", .func = cmd_faketime},
        {.command = "ntp", .help = "Salient: back to NTP time", .func = cmd_ntp},
        {.command = "fakepad", .help = "Salient: fakepad <slot> connect <kind>|disconnect|up|...|pick|back",
         .func = cmd_fakepad},
        {.command = "forget", .help = "Salient: forget <id> | all (controllers; Bluetooth pairings dropped)",
         .func = cmd_forget},
        {.command = "wifi", .help = "Salient: wifi <ssid> [password] (restarts)", .func = cmd_wifi},
        {.command = "wifi_forget", .help = "Salient: forget the network (restarts into setup)", .func = cmd_wifi_forget},
    };
    for (size_t i = 0; i < sizeof(cmds) / sizeof(cmds[0]); i++)
        esp_console_cmd_register(&cmds[i]);
}

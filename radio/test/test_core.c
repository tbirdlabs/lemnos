// Desktop tests for the radio's portable core (core/): the protocol, controllers to actions (deadzone, auto-repeat),
// the known controllers and their slots, and local time. Built and run by test/run_tests.py.
//
//   test_core                      runs the tests
//   test_core --tz-scan Y1 Y2      prints every zone's offset changes from Y1 to Y2 (run_tests.py checks them
//                                  against the IANA database)
//   test_core --transcript         prints the UART lines a scripted two-player session produces (run_tests.py
//                                  hands them to the SCORPIO side's tests)

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "known.h"
#include "link.h"
#include "pads.h"
#include "tz.h"

static int fails = 0;
static int checks = 0;

#define CHECK(cond, ...)                          \
    do {                                          \
        checks++;                                 \
        if (!(cond)) {                            \
            fails++;                              \
            printf("FAIL %s:%d: ", __FILE__, __LINE__); \
            printf(__VA_ARGS__);                  \
            printf("\n");                         \
        }                                         \
    } while (0)

// ---- link ----

static void test_link(void) {
    char out[LINK_LINE_MAX + 2];
    link_fmt_in(out, 1, ACT_UP);
    CHECK(strcmp(out, "IN p1 up\n") == 0, "IN: %s", out);
    link_fmt_in(out, 2, ACT_PICK);
    CHECK(strcmp(out, "IN p2 pick\n") == 0, "IN pick: %s", out);
    link_fmt_in(out, 4, ACT_MENU);
    CHECK(strcmp(out, "IN p4 menu\n") == 0, "IN menu: %s", out);
    link_fmt_ctl(out, 3, KIND_XAC);
    CHECK(strcmp(out, "CTL p3 connected xac\n") == 0, "CTL: %s", out);
    link_fmt_ctl(out, 3, KIND_NONE);
    CHECK(strcmp(out, "CTL p3 disconnected\n") == 0, "CTL gone: %s", out);
    link_fmt_time(out, 2026, 10, 20, 14, 5, 0);
    CHECK(strcmp(out, "TIME 2026-10-20T14:05:00\n") == 0, "TIME: %s", out);
    link_fmt_set(out, "brightness", "6");
    CHECK(strcmp(out, "SET brightness 6\n") == 0, "SET: %s", out);

    char l1[] = "HELLO 2026.10.20";
    link_msg_t m = link_parse(l1);
    CHECK(m.type == MSG_HELLO && strcmp(m.key, "2026.10.20") == 0, "HELLO");
    char l2[] = "STATE game  salient ";
    m = link_parse(l2);
    CHECK(m.type == MSG_STATE && strcmp(m.key, "game") == 0 && strcmp(m.value, "salient") == 0, "STATE: %s=%s", m.key,
          m.value);
    char l3[] = "ACK brightness";
    m = link_parse(l3);
    CHECK(m.type == MSG_ACK && strcmp(m.key, "brightness") == 0, "ACK");
    char l4[] = "GAMES clock paint salient";
    m = link_parse(l4);
    CHECK(m.type == MSG_GAMES && strcmp(m.key, "clock paint salient") == 0, "GAMES");
    char l5[] = "PAIR";
    m = link_parse(l5);
    CHECK(m.type == MSG_PAIR && strcmp(m.key, "on") == 0, "PAIR");
    char l6[] = "PAIR off";
    m = link_parse(l6);
    CHECK(m.type == MSG_PAIR && strcmp(m.key, "off") == 0, "PAIR off");
    char l7[] = "WHATEVER 1 2 3";
    CHECK(link_parse(l7).type == MSG_UNKNOWN, "unknown line");
    char l8[] = "STATE";
    CHECK(link_parse(l8).type == MSG_UNKNOWN, "STATE with no key");
    char l9[] = "";
    CHECK(link_parse(l9).type == MSG_UNKNOWN, "empty line");

    link_rx_t rx;
    link_rx_init(&rx);
    const char* in = "ACK a\r\nGAMES x\n";
    int got = 0;
    for (const char* p = in; *p; p++) {
        char* line = link_rx_byte(&rx, *p);
        if (line) {
            got++;
            CHECK(strcmp(line, got == 1 ? "ACK a" : "GAMES x") == 0, "rx line %d: %s", got, line);
        }
    }
    CHECK(got == 2, "rx: 2 lines, got %d", got);
    for (int i = 0; i < LINK_LINE_MAX + 20; i++)
        CHECK(link_rx_byte(&rx, 'x') == NULL, "long line: no line yet");
    CHECK(link_rx_byte(&rx, '\n') == NULL, "a line too long is dropped");
    char* ok = NULL;
    for (const char* p = "ACK b\n"; *p; p++)
        ok = link_rx_byte(&rx, *p) ? rx.buf : ok;
    CHECK(ok && strcmp(ok, "ACK b") == 0, "the next line after a long one is fine");
}

// ---- pads ----

typedef struct {
    int slot;
    link_action_t a;
    uint32_t t;
} ev_t;

static ev_t evs[400];
static int nev;
static uint32_t clock_ms;

static void emit(int slot, link_action_t a, void* ctx) {
    (void)ctx;
    if (nev < 400)
        evs[nev++] = (ev_t){slot, a, clock_ms};
}

static void run_to(pads_t* p, uint32_t until) {
    while (clock_ms < until) {
        clock_ms += 10;
        pads_tick(p, clock_ms);
    }
}

static void feed(pads_t* p, int slot, pad_input_t in) {
    pads_input(p, slot, &in, clock_ms);
}

static int count(int slot, link_action_t a) {
    int n = 0;
    for (int i = 0; i < nev; i++)
        if (evs[i].slot == slot && evs[i].a == a)
            n++;
    return n;
}

static void test_pads(void) {
    pads_t p;
    pads_init(&p, emit, NULL);
    nev = 0;
    clock_ms = 1000;

    // a D-pad held: once at once, again at 400 ms, then every 160 ms
    feed(&p, 1, (pad_input_t){.dirs = DIR_RIGHT});
    CHECK(nev == 1 && evs[0].a == ACT_RIGHT && evs[0].slot == 1, "D-pad: right at once");
    run_to(&p, 1000 + 1000);
    CHECK(count(1, ACT_RIGHT) == 5, "D-pad held 1 s: 5 rights (0, 400, 560, 720, 880 ms), got %d", count(1, ACT_RIGHT));
    CHECK(evs[1].t == 1400 && evs[2].t == 1560, "repeat timing: %u %u", (unsigned)evs[1].t, (unsigned)evs[2].t);
    feed(&p, 1, (pad_input_t){0});
    run_to(&p, 3000);
    CHECK(count(1, ACT_RIGHT) == 5, "released: no more");

    // the stick: a deadzone, then the same repeat as the D-pad
    nev = 0;
    feed(&p, 2, (pad_input_t){.has_stick = true, .sx = 200});
    CHECK(nev == 0, "stick inside the deadzone: nothing");
    feed(&p, 2, (pad_input_t){.has_stick = true, .sx = -100, .sy = 120});
    CHECK(nev == 0, "stick noise: nothing");
    feed(&p, 2, (pad_input_t){.has_stick = true, .sx = 300});
    CHECK(nev == 1 && evs[0].a == ACT_RIGHT, "stick pushed: right");
    feed(&p, 2, (pad_input_t){.has_stick = true, .sx = 180});
    run_to(&p, clock_ms + 450);
    CHECK(count(2, ACT_RIGHT) == 2, "stick easing back but past the release point: still held, repeats (%d)",
          count(2, ACT_RIGHT));
    feed(&p, 2, (pad_input_t){.has_stick = true, .sx = 100});
    int before = nev;
    run_to(&p, clock_ms + 1000);
    CHECK(nev == before, "stick released: no more");

    // a diagonal doesn't flicker; the other axis must lead clearly to turn
    nev = 0;
    feed(&p, 2, (pad_input_t){.has_stick = true, .sx = 300, .sy = 280});
    CHECK(nev == 1 && evs[0].a == ACT_RIGHT, "diagonal: right (x leads)");
    feed(&p, 2, (pad_input_t){.has_stick = true, .sx = 300, .sy = 350});
    feed(&p, 2, (pad_input_t){.has_stick = true, .sx = 320, .sy = 300});
    CHECK(nev == 1, "near the diagonal: stays right");
    feed(&p, 2, (pad_input_t){.has_stick = true, .sx = 300, .sy = 420});
    CHECK(nev == 2 && evs[1].a == ACT_DOWN, "y leads by 30%%: down");
    feed(&p, 2, (pad_input_t){.has_stick = true, .sx = 0, .sy = -400});
    CHECK(nev == 3 && evs[2].a == ACT_UP, "stick up: up (y negative is up)");
    feed(&p, 2, (pad_input_t){.has_stick = true});

    // pick and back on the press, once
    nev = 0;
    feed(&p, 3, (pad_input_t){.pick = true});
    feed(&p, 3, (pad_input_t){.pick = true});
    run_to(&p, clock_ms + 1000);
    feed(&p, 3, (pad_input_t){0});
    feed(&p, 3, (pad_input_t){.back = true});
    CHECK(nev == 2 && evs[0].a == ACT_PICK && evs[1].a == ACT_BACK, "pick once while held, then back");
    feed(&p, 3, (pad_input_t){0});
    feed(&p, 3, (pad_input_t){.menu = true});
    run_to(&p, clock_ms + 1000);
    feed(&p, 3, (pad_input_t){.menu = true});
    CHECK(nev == 3 && evs[2].a == ACT_MENU, "menu once while held");
    feed(&p, 3, (pad_input_t){0});

    // the D-pad wins over the stick; rolling to a second direction takes it
    nev = 0;
    feed(&p, 4, (pad_input_t){.dirs = DIR_UP, .has_stick = true, .sx = 400});
    CHECK(nev == 1 && evs[0].a == ACT_UP, "D-pad over stick: up");
    feed(&p, 4, (pad_input_t){.dirs = DIR_UP | DIR_RIGHT});
    CHECK(nev == 2 && evs[1].a == ACT_RIGHT, "roll up -> up+right: right");
    feed(&p, 4, (pad_input_t){.dirs = DIR_RIGHT});
    CHECK(nev == 2, "let go of up: still right, no new press");
    feed(&p, 4, (pad_input_t){0});

    // a slot that went away forgets what it held
    nev = 0;
    feed(&p, 5, (pad_input_t){.dirs = DIR_LEFT, .pick = true});
    pads_release(&p, 5);
    run_to(&p, clock_ms + 1000);
    CHECK(nev == 2, "released slot: no repeats (%d)", nev);
    feed(&p, 5, (pad_input_t){.pick = true});
    CHECK(nev == 3 && evs[2].a == ACT_PICK, "after release, a held pick counts as a new press");

    // out of range slots are ignored
    feed(&p, 0, (pad_input_t){.pick = true});
    feed(&p, 7, (pad_input_t){.pick = true});
    CHECK(nev == 3, "slots 0 and 7: ignored");
}

// ---- known ----

static void id(uint8_t out[6], int n) {
    uint8_t b[6] = {0xa4, 0x5e, 0x60, 0, 0, (uint8_t)n};
    memcpy(out, b, 6);
}

static void test_known(void) {
    known_table_t t;
    known_init(&t);
    uint8_t a[6], b[6], c[6], d[6];
    id(a, 1);
    id(b, 2);
    id(c, 3);
    id(d, 4);
    CHECK(known_connect(&t, a, KIND_XBOX, "Xbox Wireless Controller") == 1, "first: slot 1");
    CHECK(known_connect(&t, b, KIND_WIIMOTE, "Nintendo RVL-CNT-01") == 2, "second: slot 2");
    CHECK(known_connect(&t, c, KIND_PHONE, NULL) == 3, "third: slot 3");
    CHECK(known_connect(&t, a, KIND_XBOX, NULL) == 1, "connected again (a repeat): same slot");
    CHECK(known_disconnect(&t, b) == 2, "b leaves slot 2");
    CHECK(known_connect(&t, d, KIND_XAC, NULL) == 4, "a new one skips slot 2, which b calls its own");
    CHECK(known_connect(&t, b, KIND_WIIMOTE, NULL) == 2, "b comes back to slot 2");

    int ch[2] = {0, 0};
    CHECK(known_set_slot(&t, a, 2, ch) == 2 && ch[0] == 1 && ch[1] == 2, "a to slot 2: swaps with b");
    CHECK(known_live_slot(&t, a) == 2 && known_live_slot(&t, b) == 1, "after the swap: a in 2, b in 1");
    known_disconnect(&t, a);
    known_disconnect(&t, b);
    CHECK(known_connect(&t, b, KIND_WIIMOTE, NULL) == 1 && known_connect(&t, a, KIND_XBOX, NULL) == 2,
          "the swap is remembered");
    CHECK(known_set_slot(&t, a, 6, ch) == 2 && ch[0] == 2 && ch[1] == 6, "to an empty slot: moves");
    known_disconnect(&t, c);
    CHECK(known_set_slot(&t, c, 5, ch) == 0, "not connected: nothing to announce");
    CHECK(known_connect(&t, c, KIND_PHONE, NULL) == 5, "takes it next time");
    CHECK(known_forget(&t, c) == 5 && known_find(&t, c) < 0, "forget: gone, and it was in slot 5");
    CHECK(known_forget(&t, c) == 0, "forget twice: nothing");

    uint8_t blob[KNOWN_BLOB_MAX];
    size_t n = known_save(&t, blob, sizeof(blob));
    known_table_t u;
    CHECK(known_load(&u, blob, n), "load");
    CHECK(known_find(&u, a) >= 0 && u.k[known_find(&u, a)].slot == 6 && u.k[known_find(&u, a)].kind == KIND_XBOX,
          "a remembered in slot 6");
    CHECK(strcmp(u.k[known_find(&u, a)].name, "Xbox Wireless Controller") == 0, "name kept");
    CHECK(known_live_slot(&u, a) == 0, "after a reboot nobody is connected");
    CHECK(known_connect(&u, b, KIND_WIIMOTE, NULL) == 1, "b back in slot 1 after the reboot");
    CHECK(!known_load(&u, blob, 1) && !known_load(&u, (const uint8_t*)"\x09\x01", 2), "junk doesn't load");

    // a Wiimote's grip: upright unless set, kept through a reboot; saves from before the grip (version 1) still load
    CHECK(known_load(&u, blob, n) && u.k[known_find(&u, b)].grip == GRIP_UPRIGHT, "a Wiimote starts upright");
    uint8_t z[6];
    id(z, 99);
    CHECK(known_set_grip(&u, b, GRIP_SIDEWAYS) && !known_set_grip(&u, z, GRIP_SIDEWAYS), "grip set (known ones only)");
    n = known_save(&u, blob, sizeof(blob));
    CHECK(known_load(&t, blob, n) && t.k[known_find(&t, b)].grip == GRIP_SIDEWAYS, "grip kept");
    uint8_t v1[2 + 2 * (12 + KNOWN_NAME)] = {1, 2};
    for (int e = 0; e < 2; e++) {
        uint8_t* p = v1 + 2 + e * (12 + KNOWN_NAME);
        memcpy(p, e ? b : a, 6);
        p[6] = e ? KIND_WIIMOTE : KIND_XBOX;
        p[7] = e ? 1 : 6;
        p[11] = (uint8_t)(e + 1);
        strcpy((char*)p + 12, e ? "Nintendo RVL-CNT-01" : "Xbox Wireless Controller");
    }
    CHECK(known_load(&t, v1, sizeof(v1)), "a version 1 save loads");
    CHECK(t.k[known_find(&t, b)].slot == 1 && t.k[known_find(&t, b)].grip == GRIP_UPRIGHT &&
          strcmp(t.k[known_find(&t, b)].name, "Nintendo RVL-CNT-01") == 0 && t.k[known_find(&t, a)].slot == 6,
          "version 1: slots and names as saved, grips upright");

    // every slot taken
    known_init(&t);
    uint8_t x[6];
    for (int i = 0; i < KNOWN_SLOTS; i++) {
        id(x, 10 + i);
        known_connect(&t, x, KIND_PHONE, NULL);
    }
    id(x, 30);
    CHECK(known_connect(&t, x, KIND_PHONE, NULL) == 0 && known_find(&t, x) < 0, "seventh at once: refused");

    // the longest unused is forgotten to make room
    known_init(&t);
    for (int i = 0; i < KNOWN_MAX; i++) {
        id(x, 40 + i);
        known_connect(&t, x, KIND_PHONE, NULL);
        known_disconnect(&t, x);
    }
    id(x, 99);
    known_connect(&t, x, KIND_PHONE, NULL);
    id(x, 40);
    CHECK(known_find(&t, x) < 0, "the oldest went");
    id(x, 41);
    CHECK(known_find(&t, x) >= 0, "the next oldest stayed");

    char s[18];
    known_id_str(a, s);
    CHECK(strcmp(s, "a4:5e:60:00:00:01") == 0, "id string %s", s);
    uint8_t back[6];
    CHECK(known_id_parse(s, back) && memcmp(back, a, 6) == 0, "id parse");
    CHECK(known_id_parse("A45E60000001", back) && memcmp(back, a, 6) == 0, "id parse without colons");
    CHECK(!known_id_parse("a4:5e:60", back) && !known_id_parse("zz5e60000001", back), "bad ids");
}

// ---- tz ----

static int64_t utc(int y, int mo, int d, int h, int mi, int s) {
    return tz_days(y, mo, d) * 86400 + h * 3600 + mi * 60 + s;
}

static void test_tz(void) {
    const char* cst = "CST6CDT,M3.2.0,M11.1.0";
    bool dst;
    CHECK(tz_offset(cst, utc(2026, 3, 8, 7, 59, 59), &dst) == -6 * 3600 && !dst, "Chicago before spring forward");
    CHECK(tz_offset(cst, utc(2026, 3, 8, 8, 0, 0), &dst) == -5 * 3600 && dst, "Chicago at spring forward");
    CHECK(tz_offset(cst, utc(2026, 11, 1, 6, 59, 59), NULL) == -5 * 3600, "Chicago before fall back");
    CHECK(tz_offset(cst, utc(2026, 11, 1, 7, 0, 0), NULL) == -6 * 3600, "Chicago at fall back");
    CHECK(tz_offset("IST-5:30", 0, NULL) == 19800, "India +5:30");
    CHECK(tz_offset("NST3:30NDT,M3.2.0,M11.1.0", utc(2026, 7, 1, 0, 0, 0), NULL) == -9000, "Newfoundland summer");
    CHECK(tz_offset("<-03>3", 0, NULL) == -3 * 3600, "quoted name");
    CHECK(tz_offset("junk", 0, NULL) == 0 && tz_offset("", 0, NULL) == 0 && tz_offset(NULL, 0, NULL) == 0,
          "unreadable: UTC");
    CHECK(tz_offset("EST5EDT,M3.2.0", 0, NULL) == 0, "half a rule: unreadable");

    int y, mo, d, h, mi, s;
    tz_civil(utc(2026, 10, 20, 14, 5, 7), &y, &mo, &d, &h, &mi, &s);
    CHECK(y == 2026 && mo == 10 && d == 20 && h == 14 && mi == 5 && s == 7, "civil round trip");
    tz_civil(utc(2028, 2, 29, 23, 59, 59), &y, &mo, &d, &h, &mi, &s);
    CHECK(y == 2028 && mo == 2 && d == 29 && h == 23, "leap day");
    tz_civil(-1, &y, &mo, &d, &h, &mi, &s);
    CHECK(y == 1969 && mo == 12 && d == 31 && h == 23 && mi == 59 && s == 59, "before 1970");

    CHECK(tz_find(tz_default) >= 0, "the default zone is in the list");
    CHECK(tz_find("Nowhere/Else") < 0, "unknown zone");
    for (int i = 0; i < tz_count; i++)
        CHECK(tz_valid(tz_zones[i].posix), "%s: %s parses", tz_zones[i].id, tz_zones[i].posix);
    CHECK(!tz_valid("junk") && !tz_valid("EST5EDT,M3.2.0") && !tz_valid("EST5EDT,M13.2.0,M11.1.0"), "bad rules");
}

// Every zone's offset changes between two years: "zone utc before after", found hour by hour then to the second.
static void tz_scan(int y1, int y2) {
    for (int i = 0; i < tz_count; i++) {
        const char* r = tz_zones[i].posix;
        int64_t t = utc(y1, 1, 1, 0, 0, 0), end = utc(y2, 1, 1, 0, 0, 0);
        int32_t off = tz_offset(r, t, NULL);
        printf("%s start %d\n", tz_zones[i].id, (int)off);
        for (; t < end; t += 3600) {
            int32_t next = tz_offset(r, t + 3600, NULL);
            if (next == off)
                continue;
            int64_t lo = t, hi = t + 3600;           // off at lo, next at hi
            while (hi - lo > 1) {
                int64_t mid = lo + (hi - lo) / 2;
                if (tz_offset(r, mid, NULL) == off)
                    lo = mid;
                else
                    hi = mid;
            }
            printf("%s %lld %d %d\n", tz_zones[i].id, (long long)hi, (int)off, (int)next);
            off = next;
        }
    }
}

// ---- a scripted session, as the radio would send it ----

static char tx[64][LINK_LINE_MAX + 2];
static int ntx;

static void emit_line(int slot, link_action_t a, void* ctx) {
    (void)ctx;
    link_fmt_in(tx[ntx++ % 64], slot, a);
    fputs(tx[(ntx - 1) % 64], stdout);
}

static void transcript(void) {
    // An Xbox (left stick) as player 1 and a Wiimote (D-pad) as player 2, as in tools/test_radio.py
    char line[LINK_LINE_MAX + 2];
    pads_t p;
    pads_init(&p, emit_line, NULL);
    clock_ms = 0;
    link_fmt_hello(line, "1.0.0");
    fputs(line, stdout);
    link_fmt_set(line, "brightness", "6");
    fputs(line, stdout);
    link_fmt_time(line, 2026, 11, 1, 1, 59, 0);
    fputs(line, stdout);
    link_fmt_ctl(line, 1, KIND_XBOX);
    fputs(line, stdout);
    link_fmt_ctl(line, 2, KIND_WIIMOTE);
    fputs(line, stdout);
    pads_input(&p, 1, &(pad_input_t){.has_stick = true, .sx = 0, .sy = -400}, clock_ms);   // stick up, 0.5 s
    while (clock_ms < 500)
        pads_tick(&p, clock_ms += 10);
    pads_input(&p, 1, &(pad_input_t){.has_stick = true}, clock_ms);
    pads_input(&p, 2, &(pad_input_t){.dirs = DIR_LEFT}, clock_ms);                           // D-pad left, tap
    pads_input(&p, 2, &(pad_input_t){0}, clock_ms += 80);
    pads_input(&p, 1, &(pad_input_t){.pick = true, .has_stick = true}, clock_ms += 100);    // A: pick
    pads_input(&p, 1, &(pad_input_t){.has_stick = true}, clock_ms += 100);
    pads_input(&p, 2, &(pad_input_t){.back = true}, clock_ms += 100);                        // 1: back
    pads_input(&p, 2, &(pad_input_t){0}, clock_ms += 100);
    link_fmt_time(line, 2026, 11, 1, 1, 0, 0);                                               // fall back
    fputs(line, stdout);
    link_fmt_ctl(line, 2, KIND_NONE);
    fputs(line, stdout);
    fputs("JUNK this line means nothing\n", stdout);
}

int main(int argc, char** argv) {
    if (argc >= 4 && strcmp(argv[1], "--tz-scan") == 0) {
        tz_scan(atoi(argv[2]), atoi(argv[3]));
        return 0;
    }
    if (argc >= 2 && strcmp(argv[1], "--transcript") == 0) {
        transcript();
        return 0;
    }
    test_link();
    test_pads();
    test_known();
    test_tz();
    printf("core: %d checks, %s\n", checks, fails ? "FAILED" : "all passed");
    if (fails)
        printf("%d failed\n", fails);
    return fails ? 1 : 0;
}

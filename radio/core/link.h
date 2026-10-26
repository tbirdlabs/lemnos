// The UART protocol between the radio and the SCORPIO: 115200 8N1, newline-delimited text lines
// (docs/protocol.md). This file only builds and parses lines; the platform layer moves the bytes.
//
//   Radio -> SCORPIO                         SCORPIO -> Radio
//   HELLO <fw version>                       HELLO <fw version>
//   IN p1 up|down|left|right|pick|back|menu  STATE game rush
//   CTL p1 connected wiimote|xbox|xac|phone|gamepad   ACK <setting>
//   CTL p1 disconnected                      GAMES clock paint rush testpattern
//   TIME 2026-10-20T14:05:00                 PAIR  (or PAIR off)
//   SET brightness 6  /  SET game clock
//
// Unknown lines are ignored on both sides, so either side can add messages later.

#ifndef RADIO_LINK_H
#define RADIO_LINK_H

#include <stdbool.h>
#include <stddef.h>

#define LINK_LINE_MAX 160               // longest line either side sends, without the newline

typedef enum { ACT_NONE = 0, ACT_UP, ACT_DOWN, ACT_LEFT, ACT_RIGHT, ACT_PICK, ACT_BACK, ACT_MENU } link_action_t;

typedef enum { KIND_NONE = 0, KIND_WIIMOTE, KIND_XBOX, KIND_XAC, KIND_PHONE, KIND_GAMEPAD } link_kind_t;

const char* link_action_name(link_action_t a);
const char* link_kind_name(link_kind_t k);      // "wiimote", ...; for people: link_kind_label
const char* link_kind_label(link_kind_t k);     // "Wiimote", "Xbox", "Xbox Adaptive", "Phone", "Gamepad"

// Each formats one line, newline included, into out (at least LINK_LINE_MAX + 2 bytes); returns its length.
int link_fmt_in(char* out, int slot, link_action_t a);
int link_fmt_ctl(char* out, int slot, link_kind_t kind);         // KIND_NONE = disconnected
int link_fmt_time(char* out, int y, int mo, int d, int h, int mi, int s);
int link_fmt_set(char* out, const char* key, const char* value);
int link_fmt_hello(char* out, const char* version);

// Lines from the SCORPIO
typedef enum { MSG_UNKNOWN = 0, MSG_HELLO, MSG_STATE, MSG_ACK, MSG_GAMES, MSG_PAIR } link_msg_type_t;

typedef struct {
    link_msg_type_t type;
    const char* key;               // HELLO: the version; STATE, ACK: the key; GAMES: the list; PAIR: "on"/"off"
    const char* value;             // STATE: the value
} link_msg_t;

// Parses a line (no newline) in place: it's cut into words, so msg points into it.
link_msg_t link_parse(char* line);

// Gathers bytes into lines. Lines longer than LINK_LINE_MAX are dropped whole; \r is ignored.
typedef struct {
    char buf[LINK_LINE_MAX + 1];
    int len;
    bool overflow;
} link_rx_t;

void link_rx_init(link_rx_t* rx);
// Feeds one byte; returns the finished line (no newline, NUL-terminated, valid until the next call) or NULL.
char* link_rx_byte(link_rx_t* rx, char c);

#endif

#include "link.h"

#include <stdio.h>
#include <string.h>

static const char* const ACTIONS[] = {"", "up", "down", "left", "right", "pick", "back"};
static const char* const KINDS[] = {"", "wiimote", "xbox", "xac", "phone", "gamepad"};
static const char* const LABELS[] = {"", "Wiimote", "Xbox", "Xbox Adaptive", "Phone", "Gamepad"};

const char* link_action_name(link_action_t a) {
    return a > ACT_NONE && a <= ACT_BACK ? ACTIONS[a] : "";
}

const char* link_kind_name(link_kind_t k) {
    return k > KIND_NONE && k <= KIND_GAMEPAD ? KINDS[k] : "";
}

const char* link_kind_label(link_kind_t k) {
    return k > KIND_NONE && k <= KIND_GAMEPAD ? LABELS[k] : "";
}

int link_fmt_in(char* out, int slot, link_action_t a) {
    return snprintf(out, LINK_LINE_MAX + 2, "IN p%d %s\n", slot, link_action_name(a));
}

int link_fmt_ctl(char* out, int slot, link_kind_t kind) {
    if (kind == KIND_NONE)
        return snprintf(out, LINK_LINE_MAX + 2, "CTL p%d disconnected\n", slot);
    return snprintf(out, LINK_LINE_MAX + 2, "CTL p%d connected %s\n", slot, link_kind_name(kind));
}

int link_fmt_time(char* out, int y, int mo, int d, int h, int mi, int s) {
    return snprintf(out, LINK_LINE_MAX + 2, "TIME %04d-%02d-%02dT%02d:%02d:%02d\n", y, mo, d, h, mi, s);
}

int link_fmt_set(char* out, const char* key, const char* value) {
    return snprintf(out, LINK_LINE_MAX + 2, "SET %s %s\n", key, value);
}

int link_fmt_hello(char* out, const char* version) {
    return snprintf(out, LINK_LINE_MAX + 2, "HELLO %s\n", version);
}

static char* skip_spaces(char* s) {
    while (*s == ' ' || *s == '\t')
        s++;
    return s;
}

// The next word of *s, cut off with a NUL; *s moves past it. "" at the end.
static char* word(char** s) {
    char* w = skip_spaces(*s);
    char* e = w;
    while (*e && *e != ' ' && *e != '\t')
        e++;
    if (*e)
        *e++ = 0;
    *s = e;
    return w;
}

// The rest of the line, trimmed.
static char* rest(char* s) {
    s = skip_spaces(s);
    int n = (int)strlen(s);
    while (n > 0 && (s[n - 1] == ' ' || s[n - 1] == '\t'))
        s[--n] = 0;
    return s;
}

link_msg_t link_parse(char* line) {
    link_msg_t m = {MSG_UNKNOWN, "", ""};
    char* s = line;
    char* cmd = word(&s);
    if (strcmp(cmd, "HELLO") == 0) {
        m.type = MSG_HELLO;
        m.key = rest(s);
    } else if (strcmp(cmd, "STATE") == 0) {
        m.key = word(&s);
        m.value = rest(s);
        if (*m.key)
            m.type = MSG_STATE;
    } else if (strcmp(cmd, "ACK") == 0) {
        m.type = MSG_ACK;
        m.key = rest(s);
    } else if (strcmp(cmd, "GAMES") == 0) {
        m.type = MSG_GAMES;
        m.key = rest(s);
    } else if (strcmp(cmd, "PAIR") == 0) {
        m.type = MSG_PAIR;
        char* w = word(&s);
        m.key = strcmp(w, "off") == 0 ? "off" : "on";
    }
    return m;
}

void link_rx_init(link_rx_t* rx) {
    rx->len = 0;
    rx->overflow = false;
}

char* link_rx_byte(link_rx_t* rx, char c) {
    if (c == '\r')
        return NULL;
    if (c == '\n') {
        bool bad = rx->overflow;
        rx->buf[rx->len] = 0;
        rx->len = 0;
        rx->overflow = false;
        return bad ? NULL : rx->buf;
    }
    if (rx->len >= LINK_LINE_MAX) {
        rx->overflow = true;
        return NULL;
    }
    rx->buf[rx->len++] = c;
    return NULL;
}

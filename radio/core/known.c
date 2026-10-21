#include "known.h"

#include <stdio.h>
#include <string.h>

#define BLOB_VERSION 2                     // 2 added the grip byte; a version 1 blob still loads (every grip upright)
#define ENTRY_V1 (6 + 1 + 1 + 4 + KNOWN_NAME)
#define ENTRY (ENTRY_V1 + 1)

void known_init(known_table_t* t) {
    memset(t, 0, sizeof(*t));
    for (int s = 0; s <= KNOWN_SLOTS; s++)
        t->live[s] = -1;
}

int known_find(const known_table_t* t, const uint8_t id[6]) {
    for (int i = 0; i < KNOWN_MAX; i++)
        if (t->k[i].used && memcmp(t->k[i].id, id, 6) == 0)
            return i;
    return -1;
}

bool known_is_live(const known_table_t* t, int index) {
    if (index < 0)
        return false;
    for (int s = 1; s <= KNOWN_SLOTS; s++)
        if (t->live[s] == index)
            return true;
    return false;
}

int known_live_slot(const known_table_t* t, const uint8_t id[6]) {
    int i = known_find(t, id);
    if (i < 0)
        return 0;
    for (int s = 1; s <= KNOWN_SLOTS; s++)
        if (t->live[s] == i)
            return s;
    return 0;
}

static bool remembered_by_other(const known_table_t* t, int slot, int except) {
    for (int i = 0; i < KNOWN_MAX; i++)
        if (i != except && t->k[i].used && t->k[i].slot == slot)
            return true;
    return false;
}

static int free_slot(const known_table_t* t, int except) {
    for (int s = 1; s <= KNOWN_SLOTS; s++)          // first a slot nobody else calls theirs
        if (t->live[s] < 0 && !remembered_by_other(t, s, except))
            return s;
    for (int s = 1; s <= KNOWN_SLOTS; s++)
        if (t->live[s] < 0)
            return s;
    return 0;
}

// A free entry: an unused one, else the longest unused that isn't connected.
static int new_entry(known_table_t* t) {
    int best = -1;
    for (int i = 0; i < KNOWN_MAX; i++) {
        if (!t->k[i].used)
            return i;
        if (!known_is_live(t, i) && (best < 0 || t->k[i].seen < t->k[best].seen))
            best = i;
    }
    return best;
}

int known_connect(known_table_t* t, const uint8_t id[6], link_kind_t kind, const char* name) {
    int i = known_find(t, id);
    int slot = known_live_slot(t, id);
    if (slot)
        return slot;                                 // already connected (a repeat)
    if (i >= 0 && t->k[i].slot >= 1 && t->k[i].slot <= KNOWN_SLOTS && t->live[t->k[i].slot] < 0)
        slot = t->k[i].slot;
    else
        slot = free_slot(t, i);
    if (!slot)
        return 0;
    if (i < 0) {
        i = new_entry(t);
        if (i < 0)
            return 0;
        memset(&t->k[i], 0, sizeof(known_t));
        t->k[i].used = true;
        memcpy(t->k[i].id, id, 6);
    }
    known_t* e = &t->k[i];
    e->kind = (uint8_t)kind;
    if (name && *name) {
        strncpy(e->name, name, KNOWN_NAME - 1);
        e->name[KNOWN_NAME - 1] = 0;
    }
    e->slot = (uint8_t)slot;
    e->seen = ++t->clock;
    t->live[slot] = (int8_t)i;
    return slot;
}

int known_disconnect(known_table_t* t, const uint8_t id[6]) {
    int slot = known_live_slot(t, id);
    if (slot)
        t->live[slot] = -1;
    return slot;
}

int known_set_slot(known_table_t* t, const uint8_t id[6], int slot, int changed[2]) {
    int i = known_find(t, id);
    if (i < 0 || slot < 1 || slot > KNOWN_SLOTS)
        return 0;
    int old = known_live_slot(t, id);
    if (old == slot)
        return 0;
    if (!old) {                                      // not playing now: it takes the slot next time
        t->k[i].slot = (uint8_t)slot;
        return 0;
    }
    int other = t->live[slot];
    t->live[slot] = (int8_t)i;
    t->live[old] = (int8_t)other;
    t->k[i].slot = (uint8_t)slot;
    if (other >= 0)
        t->k[other].slot = (uint8_t)old;
    changed[0] = old;
    changed[1] = slot;
    return 2;
}

int known_forget(known_table_t* t, const uint8_t id[6]) {
    int i = known_find(t, id);
    if (i < 0)
        return 0;
    int slot = known_disconnect(t, id);
    memset(&t->k[i], 0, sizeof(known_t));
    return slot;
}

bool known_set_grip(known_table_t* t, const uint8_t id[6], int grip) {
    int i = known_find(t, id);
    if (i < 0)
        return false;
    t->k[i].grip = grip == GRIP_SIDEWAYS ? GRIP_SIDEWAYS : GRIP_UPRIGHT;
    return true;
}

size_t known_save(const known_table_t* t, uint8_t* buf, size_t max) {
    if (max < 2)
        return 0;
    size_t n = 2;
    int count = 0;
    for (int i = 0; i < KNOWN_MAX && n + ENTRY <= max; i++) {
        const known_t* e = &t->k[i];
        if (!e->used)
            continue;
        memcpy(buf + n, e->id, 6);
        buf[n + 6] = e->kind;
        buf[n + 7] = e->slot;
        buf[n + 8] = (uint8_t)(e->seen >> 24);
        buf[n + 9] = (uint8_t)(e->seen >> 16);
        buf[n + 10] = (uint8_t)(e->seen >> 8);
        buf[n + 11] = (uint8_t)e->seen;
        memcpy(buf + n + 12, e->name, KNOWN_NAME);
        buf[n + 12 + KNOWN_NAME] = e->grip;
        n += ENTRY;
        count++;
    }
    buf[0] = BLOB_VERSION;
    buf[1] = (uint8_t)count;
    return n;
}

bool known_load(known_table_t* t, const uint8_t* buf, size_t len) {
    known_init(t);
    if (len < 2 || (buf[0] != 1 && buf[0] != BLOB_VERSION) || buf[1] > KNOWN_MAX)
        return false;
    size_t entry = buf[0] == 1 ? ENTRY_V1 : ENTRY;
    if (len < 2 + (size_t)buf[1] * entry)
        return false;
    for (int i = 0; i < buf[1]; i++) {
        const uint8_t* p = buf + 2 + i * entry;
        known_t* e = &t->k[i];
        e->used = true;
        memcpy(e->id, p, 6);
        e->kind = p[6] <= KIND_GAMEPAD ? p[6] : KIND_GAMEPAD;
        e->slot = p[7] >= 1 && p[7] <= KNOWN_SLOTS ? p[7] : 1;
        e->seen = (uint32_t)p[8] << 24 | (uint32_t)p[9] << 16 | (uint32_t)p[10] << 8 | p[11];
        memcpy(e->name, p + 12, KNOWN_NAME);
        e->name[KNOWN_NAME - 1] = 0;
        e->grip = entry == ENTRY && p[12 + KNOWN_NAME] == GRIP_SIDEWAYS ? GRIP_SIDEWAYS : GRIP_UPRIGHT;
        if (e->seen > t->clock)
            t->clock = e->seen;
    }
    return true;
}

void known_id_str(const uint8_t id[6], char out[18]) {
    snprintf(out, 18, "%02x:%02x:%02x:%02x:%02x:%02x", id[0], id[1], id[2], id[3], id[4], id[5]);
}

static int hexval(char c) {
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    if (c >= 'A' && c <= 'F')
        return c - 'A' + 10;
    return -1;
}

bool known_id_parse(const char* s, uint8_t id[6]) {
    // "a4:5e:60:12:34:56", or 12 hex digits with no colons (a phone's id)
    for (int i = 0; i < 6; i++) {
        int hi = hexval(s[0]), lo = hi < 0 ? -1 : hexval(s[1]);
        if (hi < 0 || lo < 0)
            return false;
        id[i] = (uint8_t)(hi << 4 | lo);
        s += 2;
        if (i < 5 && *s == ':')
            s++;
    }
    return *s == 0;
}

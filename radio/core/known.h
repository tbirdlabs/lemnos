// The controllers the radio knows (paired Bluetooth controllers, and phones by the id their page keeps) and the
// player slot each one plays in. Saved across reboots (the platform layer stores known_save()'s bytes).
//
// A controller keeps its slot: it comes back to it on reconnecting, unless someone else is playing in it then.
// Slots are p1..p6 (the board's six seats); up to KNOWN_MAX controllers are remembered, the longest unused forgotten
// first. Not thread-safe: the caller serializes calls.

#ifndef RADIO_KNOWN_H
#define RADIO_KNOWN_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "link.h"

#define KNOWN_MAX 12
#define KNOWN_SLOTS 6
#define KNOWN_NAME 32
#define KNOWN_BLOB_MAX (2 + KNOWN_MAX * (6 + 1 + 1 + 4 + KNOWN_NAME + 1))

// How a Wiimote is held (bt.c maps its buttons to match). Other controllers ignore it.
#define GRIP_UPRIGHT 0                 // one hand: D-pad on top, A = pick, B (the trigger) = back
#define GRIP_SIDEWAYS 1                // two hands: D-pad on the left, 2 = pick, 1 = back

typedef struct {
    bool used;
    uint8_t id[6];                     // Bluetooth address, or a phone's id
    uint8_t kind;                      // link_kind_t
    uint8_t slot;                      // the slot it plays in, 1..KNOWN_SLOTS
    uint32_t seen;                     // when it last connected, in connections (higher = more recent)
    char name[KNOWN_NAME];             // the device's own name, if it gave one
    uint8_t grip;                      // GRIP_UPRIGHT or GRIP_SIDEWAYS
} known_t;

typedef struct {
    known_t k[KNOWN_MAX];
    int8_t live[KNOWN_SLOTS + 1];      // by slot: index into k of the controller playing there, or -1
    uint32_t clock;
} known_table_t;

void known_init(known_table_t* t);
int known_find(const known_table_t* t, const uint8_t id[6]);           // index, or -1
bool known_is_live(const known_table_t* t, int index);
int known_live_slot(const known_table_t* t, const uint8_t id[6]);      // its slot if connected, else 0

// A controller connected: remembered if new. Returns its slot, or 0 if every slot is taken (then it isn't added).
int known_connect(known_table_t* t, const uint8_t id[6], link_kind_t kind, const char* name);
// It disconnected: returns the slot it left, or 0 if it wasn't connected.
int known_disconnect(known_table_t* t, const uint8_t id[6]);
// Moves it to another slot. If someone is playing in that slot, the two swap. changed[] gets the slots whose
// player changed (0, 1 or 2 of them; the return value says how many) so the caller can announce them.
int known_set_slot(known_table_t* t, const uint8_t id[6], int slot, int changed[2]);
// How it's held (GRIP_*). False if it isn't known.
bool known_set_grip(known_table_t* t, const uint8_t id[6], int grip);
// Forgets it. Returns the slot it was connected in (the caller disconnects it), or 0.
int known_forget(known_table_t* t, const uint8_t id[6]);

size_t known_save(const known_table_t* t, uint8_t* buf, size_t max);  // bytes written (KNOWN_BLOB_MAX is enough)
bool known_load(known_table_t* t, const uint8_t* buf, size_t len);     // false (and empty) if it isn't one

// "a4:5e:60:12:34:56" (18 bytes with the NUL) and back
void known_id_str(const uint8_t id[6], char out[18]);
bool known_id_parse(const char* s, uint8_t id[6]);

#endif

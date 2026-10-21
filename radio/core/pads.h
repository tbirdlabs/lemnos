// Controllers in, actions out. Every controller, whatever it is, comes here as a pad_input (directions held, the
// left stick, pick and back held) and leaves as actions: up/down/left/right, pick, back. The platform layer maps a
// device's own buttons to pick and back (bt.c: a Wiimote's 2 and 1, an Xbox's A and B); this file adds the stick's
// deadzone and turns a held direction, from the D-pad or the stick, into the same auto-repeat.
//
// Not thread-safe: the caller serializes calls (the ESP32 build holds the hub lock).

#ifndef RADIO_PADS_H
#define RADIO_PADS_H

#include <stdbool.h>
#include <stdint.h>

#include "link.h"

#define PADS_MAX 6                     // one per player slot

// Directions held (bits)
#define DIR_UP 1
#define DIR_DOWN 2
#define DIR_LEFT 4
#define DIR_RIGHT 8

// Feel: tuned to match a D-pad. A direction moves once at once, again after REPEAT_DELAY, then every REPEAT_EVERY.
#define PADS_REPEAT_DELAY_MS 400
#define PADS_REPEAT_EVERY_MS 160
// The stick (axes -512..511, y down positive): it counts as pushed past STICK_ON of full travel, released below
// STICK_OFF, so it doesn't chatter at the edge; a push changes direction only when the other axis leads by
// STICK_TURN (a diagonal doesn't flicker between two).
#define PADS_STICK_ON 230
#define PADS_STICK_OFF 150
#define PADS_STICK_TURN_PCT 130

typedef struct {
    uint8_t dirs;                      // DIR_* bits held on the D-pad (or the phone's)
    bool has_stick;
    int16_t sx, sy;                    // the left stick, -512..511 (y: down is positive), if has_stick
    bool pick, back;                   // held
} pad_input_t;

typedef void (*pads_emit_t)(int slot, link_action_t a, void* ctx);

typedef struct {
    bool used;
    uint8_t dpad_dir;                  // the direction the D-pad gives (one DIR_* bit or 0)
    uint8_t stick_dir;                 // the direction the stick gives
    uint8_t dirs_before;               // the D-pad bits last time, to see which one is new
    uint8_t held;                      // the direction acted on (one DIR_* bit or 0)
    uint32_t next_repeat;              // when it repeats next
    bool pick, back;
} pad_state_t;

typedef struct {
    pad_state_t pad[PADS_MAX + 1];     // by slot, 1..PADS_MAX
    pads_emit_t emit;
    void* ctx;
} pads_t;

void pads_init(pads_t* p, pads_emit_t emit, void* ctx);
// A controller's state now (call on every report; unchanged reports are fine). now: milliseconds, any origin.
void pads_input(pads_t* p, int slot, const pad_input_t* in, uint32_t now);
// Call often (every 10 ms or so): sends the repeats that are due.
void pads_tick(pads_t* p, uint32_t now);
// The controller in this slot went away: forget what it held (nothing is sent).
void pads_release(pads_t* p, int slot);

#endif

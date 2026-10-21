#include "pads.h"

#include <stdlib.h>
#include <string.h>

static const uint8_t ORDER[] = {DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT};    // which wins when two are new at once

static link_action_t dir_action(uint8_t d) {
    switch (d) {
        case DIR_UP:
            return ACT_UP;
        case DIR_DOWN:
            return ACT_DOWN;
        case DIR_LEFT:
            return ACT_LEFT;
        case DIR_RIGHT:
            return ACT_RIGHT;
    }
    return ACT_NONE;
}

static uint8_t first_bit(uint8_t bits) {
    for (unsigned i = 0; i < sizeof(ORDER); i++)
        if (bits & ORDER[i])
            return ORDER[i];
    return 0;
}

// The D-pad's direction: a newly pressed one takes over; while the one acted on stays down it stays (rolling the
// thumb from up to up+right keeps up until up lets go, then right).
static uint8_t dpad_dir(pad_state_t* s, uint8_t dirs) {
    uint8_t fresh = dirs & ~s->dirs_before;
    s->dirs_before = dirs;
    if (!dirs)
        return 0;
    if (fresh)
        return first_bit(fresh);
    if (dirs & s->dpad_dir)
        return s->dpad_dir;
    return first_bit(dirs);
}

static uint8_t stick_dir(const pad_state_t* s, int x, int y) {
    long r2 = (long)x * x + (long)y * y;
    uint8_t cur = s->stick_dir;
    long limit = cur ? PADS_STICK_OFF : PADS_STICK_ON;
    if (r2 < limit * limit)
        return 0;
    int ax = abs(x), ay = abs(y);
    uint8_t h = x < 0 ? DIR_LEFT : DIR_RIGHT;
    uint8_t v = y < 0 ? DIR_UP : DIR_DOWN;
    if (!cur)
        return ax >= ay ? h : v;
    if (cur & (DIR_LEFT | DIR_RIGHT))
        return (long)ay * 100 > (long)ax * PADS_STICK_TURN_PCT ? v : h;
    return (long)ax * 100 > (long)ay * PADS_STICK_TURN_PCT ? h : v;
}

void pads_init(pads_t* p, pads_emit_t emit, void* ctx) {
    memset(p, 0, sizeof(*p));
    p->emit = emit;
    p->ctx = ctx;
}

void pads_input(pads_t* p, int slot, const pad_input_t* in, uint32_t now) {
    if (slot < 1 || slot > PADS_MAX)
        return;
    pad_state_t* s = &p->pad[slot];
    s->used = true;
    s->dpad_dir = dpad_dir(s, in->dirs);
    s->stick_dir = in->has_stick ? stick_dir(s, in->sx, in->sy) : 0;
    uint8_t held = s->dpad_dir ? s->dpad_dir : s->stick_dir;
    if (held != s->held) {
        s->held = held;
        if (held) {
            p->emit(slot, dir_action(held), p->ctx);
            s->next_repeat = now + PADS_REPEAT_DELAY_MS;
        }
    }
    if (in->pick && !s->pick)
        p->emit(slot, ACT_PICK, p->ctx);
    if (in->back && !s->back)
        p->emit(slot, ACT_BACK, p->ctx);
    s->pick = in->pick;
    s->back = in->back;
}

void pads_tick(pads_t* p, uint32_t now) {
    for (int slot = 1; slot <= PADS_MAX; slot++) {
        pad_state_t* s = &p->pad[slot];
        if (!s->used || !s->held || (int32_t)(now - s->next_repeat) < 0)
            continue;
        p->emit(slot, dir_action(s->held), p->ctx);
        s->next_repeat += PADS_REPEAT_EVERY_MS;
        if ((int32_t)(now - s->next_repeat) >= 0)      // fell behind (a stall): no burst to catch up
            s->next_repeat = now + PADS_REPEAT_EVERY_MS;
    }
}

void pads_release(pads_t* p, int slot) {
    if (slot >= 1 && slot <= PADS_MAX)
        memset(&p->pad[slot], 0, sizeof(pad_state_t));
}

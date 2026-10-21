// Bluetooth controllers through Bluepad32 (its "custom platform"): who may connect, what kind each one is, and its
// buttons mapped to move / pick / back. Bluepad32 runs on BTstack's thread; these calls are safe from any task.
#pragma once

#include <stdbool.h>
#include <stdint.h>

struct uni_platform* bt_platform(void);
void bt_pair(bool on);                 // pairing mode: new controllers may connect, for BT_PAIR_SECONDS
int bt_pairing_left(void);             // seconds of pairing mode left, 0 = off
void bt_forget(const uint8_t id[6]);   // disconnect it, drop its pairing keys, forget it

#define BT_PAIR_SECONDS 60

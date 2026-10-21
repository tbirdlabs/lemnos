// Settings and known controllers in flash (NVS namespace "salient"). Bluepad32/BTstack keep the pairing keys
// themselves, in their own NVS namespaces.
#pragma once

#include "hub.h"

void store_init(void);
void store_load(radio_settings_t* s, known_table_t* k);
void store_save_settings(const radio_settings_t* s);
void store_save_known(const known_table_t* k);

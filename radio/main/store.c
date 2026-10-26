#include "store.h"

#include <stdbool.h>
#include <string.h>

#include "esp_log.h"
#include "nvs.h"
#include "nvs_flash.h"

static const char* TAG = "store";
static const char* NS = "lemnos";
static const char* OLD_NS = "salient";            // before the board was named Lemnos (radio 1.1.0 and older)

void store_init(void) {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS needs erasing (%s); settings start over", esp_err_to_name(err));
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
}

static void get_str(nvs_handle_t h, const char* key, char* out, size_t n) {
    size_t len = n;
    if (nvs_get_str(h, key, out, &len) != ESP_OK)
        out[0] = 0;
}

static bool load_from(const char* ns, radio_settings_t* s, known_table_t* k) {
    nvs_handle_t h;
    if (nvs_open(ns, NVS_READONLY, &h) != ESP_OK)
        return false;
    get_str(h, "tz", s->tz, sizeof(s->tz));
    get_str(h, "game", s->game, sizeof(s->game));
    get_str(h, "ssid", s->ssid, sizeof(s->ssid));
    get_str(h, "pass", s->pass, sizeof(s->pass));
    int8_t b = 0;
    if (nvs_get_i8(h, "bright", &b) == ESP_OK && b >= 0 && b <= 10)
        s->brightness = b;
    static uint8_t blob[KNOWN_BLOB_MAX];
    size_t len = sizeof(blob);
    if (nvs_get_blob(h, "known", blob, &len) == ESP_OK && !known_load(k, blob, len))
        ESP_LOGW(TAG, "saved controllers unreadable; starting with none");
    nvs_close(h);
    return true;
}

void store_load(radio_settings_t* s, known_table_t* k) {
    memset(s, 0, sizeof(*s));
    known_init(k);
    if (load_from(NS, s, k) || !load_from(OLD_NS, s, k))
        return;                                      // (neither: first boot)
    ESP_LOGI(TAG, "moving the settings from \"%s\" to \"%s\"", OLD_NS, NS);
    store_save_settings(s);
    store_save_known(k);
    nvs_handle_t h;
    if (nvs_open(OLD_NS, NVS_READWRITE, &h) == ESP_OK) {
        nvs_erase_all(h);
        nvs_commit(h);
        nvs_close(h);
    }
}

void store_save_settings(const radio_settings_t* s) {
    nvs_handle_t h;
    if (nvs_open(NS, NVS_READWRITE, &h) != ESP_OK)
        return;
    nvs_set_str(h, "tz", s->tz);
    nvs_set_str(h, "game", s->game);
    nvs_set_str(h, "ssid", s->ssid);
    nvs_set_str(h, "pass", s->pass);
    nvs_set_i8(h, "bright", (int8_t)s->brightness);
    if (nvs_commit(h) != ESP_OK)
        ESP_LOGE(TAG, "saving settings failed");
    nvs_close(h);
}

void store_save_known(const known_table_t* k) {
    static uint8_t blob[KNOWN_BLOB_MAX];
    size_t len = known_save(k, blob, sizeof(blob));
    nvs_handle_t h;
    if (nvs_open(NS, NVS_READWRITE, &h) != ESP_OK)
        return;
    nvs_set_blob(h, "known", blob, len);
    if (nvs_commit(h) != ESP_OK)
        ESP_LOGE(TAG, "saving controllers failed");
    nvs_close(h);
}

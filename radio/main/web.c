// API (all JSON):
//   GET  /api/state[?zones=1]   everything the settings page shows (zones=1 adds the time zone list)
//   POST /api/settings          {"brightness": 0-10 (0 = the board's own), "game": "clock", "tz": "America/Chicago"}
//   POST /api/pair              {"on": true}
//   POST /api/controller        {"id": "a4:5e:...", "slot": 3}  or  {"id": ..., "forget": true}
//                               or  {"id": ..., "grip": "upright"|"sideways"} (a Wiimote: how it's held)
//   GET  /api/scan              WiFi networks in range
//   POST /api/wifi              {"ssid": ..., "pass": ...}: saves and restarts
//   POST /api/wifi_forget       forgets the network and restarts into setup
// Phone controller, WebSocket /ws, text frames:
//   phone -> radio   "hello <12 hex digits>" (its id, kept in the phone's browser), "s <dirs> <pick> <back>" (what's
//                    held: dirs = up 1, down 2, left 4, right 8), "k" (still here, every 2 s)
//   radio -> phone   "slot <n>", or "full" (every slot taken)

#include "web.h"

#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include "board.h"
#include "bt.h"
#include "cJSON.h"
#include "clock.h"
#include "esp_heap_caps.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "hub.h"
#include "net.h"
#include "tz.h"

#define PHONE_QUIET_MS 6000            // a phone page that sends nothing this long is gone (screen off, walked off)

static const char* TAG = "web";

extern const char index_html[] asm("_binary_index_html_start");
extern const char pad_html[] asm("_binary_pad_html_start");

static httpd_handle_t server;

typedef struct {
    bool used;
    int fd;
    uint8_t id[6];
    uint32_t last;
} phone_t;

static phone_t phones[KNOWN_SLOTS];   // guarded by the hub lock

// ---- helpers ----

static esp_err_t send_json(httpd_req_t* r, cJSON* j) {
    char* s = cJSON_PrintUnformatted(j);
    cJSON_Delete(j);
    httpd_resp_set_type(r, "application/json");
    httpd_resp_set_hdr(r, "Cache-Control", "no-store");
    esp_err_t e = httpd_resp_sendstr(r, s ? s : "{}");
    free(s);
    return e;
}

static esp_err_t ok(httpd_req_t* r) {
    cJSON* j = cJSON_CreateObject();
    cJSON_AddBoolToObject(j, "ok", true);
    return send_json(r, j);
}

static esp_err_t fail(httpd_req_t* r, const char* why) {
    httpd_resp_set_status(r, "400 Bad Request");
    cJSON* j = cJSON_CreateObject();
    cJSON_AddStringToObject(j, "error", why);
    return send_json(r, j);
}

static cJSON* read_json(httpd_req_t* r) {
    int len = r->content_len;
    if (len <= 0 || len > 1024)
        return NULL;
    char* buf = malloc(len + 1);
    if (!buf)
        return NULL;
    int got = 0;
    while (got < len) {
        int n = httpd_req_recv(r, buf + got, len - got);
        if (n <= 0) {
            free(buf);
            return NULL;
        }
        got += n;
    }
    buf[len] = 0;
    cJSON* j = cJSON_Parse(buf);
    free(buf);
    return j;
}

static const char* str_of(cJSON* j, const char* key) {
    cJSON* v = cJSON_GetObjectItem(j, key);
    return cJSON_IsString(v) ? v->valuestring : NULL;
}

// ---- pages ----

static esp_err_t page_index(httpd_req_t* r) {
    httpd_resp_set_type(r, "text/html; charset=utf-8");
    return httpd_resp_sendstr(r, index_html);
}

static esp_err_t page_pad(httpd_req_t* r) {
    httpd_resp_set_type(r, "text/html; charset=utf-8");
    return httpd_resp_sendstr(r, pad_html);
}

static esp_err_t no_content(httpd_req_t* r) {
    httpd_resp_set_status(r, "204 No Content");
    return httpd_resp_send(r, NULL, 0);
}

// Captive portal: on the setup network, anything unknown (a phone checking for internet) goes to the settings page
static esp_err_t not_found(httpd_req_t* r, httpd_err_code_t err) {
    (void)err;
    if (net_ap_active()) {
        httpd_resp_set_status(r, "302 Found");
        httpd_resp_set_hdr(r, "Location", "http://192.168.4.1/");
        return httpd_resp_send(r, NULL, 0);
    }
    httpd_resp_send_err(r, HTTPD_404_NOT_FOUND, "Not here");
    return ESP_FAIL;
}

// ---- API ----

static esp_err_t api_state(httpd_req_t* r) {
    char q[32] = "";
    bool zones = httpd_req_get_url_query_str(r, q, sizeof(q)) == ESP_OK && strstr(q, "zones=1");
    cJSON* j = cJSON_CreateObject();
    cJSON_AddStringToObject(j, "fw", RADIO_FW_VERSION);
    cJSON_AddStringToObject(j, "board", BOARD_NAME);
    cJSON_AddNumberToObject(j, "uptime", hub_ms() / 1000);

    net_status_t ns;
    net_status(&ns);
    cJSON* w = cJSON_AddObjectToObject(j, "wifi");
    cJSON_AddBoolToObject(w, "connected", ns.connected);
    cJSON_AddStringToObject(w, "ssid", ns.ssid);
    cJSON_AddStringToObject(w, "ip", ns.ip);
    cJSON_AddNumberToObject(w, "rssi", ns.rssi);
    cJSON_AddBoolToObject(w, "setup", ns.ap_on);
    cJSON_AddStringToObject(w, "setup_name", ns.ap_ssid);
    cJSON_AddStringToObject(w, "host", "lemnos.local");

    cJSON* t = cJSON_AddObjectToObject(j, "time");
    cJSON_AddStringToObject(t, "source", clock_source());
    int64_t local;
    bool dst;
    if (clock_local(&local, &dst)) {
        int y, mo, d, h, mi, s;
        char buf[24];
        tz_civil(local, &y, &mo, &d, &h, &mi, &s);
        snprintf(buf, sizeof(buf), "%04d-%02d-%02d %02d:%02d:%02d", y, mo, d, h, mi, s);
        cJSON_AddStringToObject(t, "local", buf);
        cJSON_AddBoolToObject(t, "dst", dst);
    }

    cJSON_AddNumberToObject(j, "pairing", bt_pairing_left());
    cJSON_AddNumberToObject(j, "slots", KNOWN_SLOTS);

    hub_lock();
    cJSON* st = cJSON_AddObjectToObject(j, "settings");
    cJSON_AddStringToObject(st, "tz", hub_settings.tz);
    cJSON_AddNumberToObject(st, "brightness", hub_settings.brightness);
    cJSON_AddStringToObject(st, "game", hub_settings.game);

    cJSON* b = cJSON_AddObjectToObject(j, "scorpio");
    cJSON_AddBoolToObject(b, "seen", hub_board.seen);
    cJSON_AddStringToObject(b, "fw", hub_board.fw);
    cJSON_AddStringToObject(b, "game", hub_board.game);
    cJSON* games = cJSON_AddArrayToObject(b, "games");
    char list[sizeof(hub_board.games)];
    strcpy(list, hub_board.games);
    for (char* g = strtok(list, " "); g; g = strtok(NULL, " "))
        cJSON_AddItemToArray(games, cJSON_CreateString(g));
    if (hub_board.seen)
        cJSON_AddNumberToObject(b, "quiet_s", (hub_ms() - hub_board.last_ms) / 1000);

    cJSON* cs = cJSON_AddArrayToObject(j, "controllers");
    for (int i = 0; i < KNOWN_MAX; i++) {
        known_t* e = &hub_known.k[i];
        if (!e->used)
            continue;
        char id[18];
        known_id_str(e->id, id);
        cJSON* c = cJSON_CreateObject();
        cJSON_AddStringToObject(c, "id", id);
        cJSON_AddStringToObject(c, "kind", link_kind_name(e->kind));
        cJSON_AddStringToObject(c, "label", link_kind_label(e->kind));
        cJSON_AddStringToObject(c, "name", e->name);
        cJSON_AddNumberToObject(c, "slot", e->slot);
        if (e->kind == KIND_WIIMOTE)
            cJSON_AddStringToObject(c, "grip", e->grip == GRIP_SIDEWAYS ? "sideways" : "upright");
        cJSON_AddBoolToObject(c, "connected", known_is_live(&hub_known, i));
        cJSON_AddNumberToObject(c, "seen", e->seen);
        cJSON_AddItemToArray(cs, c);
    }
    hub_unlock();

    if (zones) {
        cJSON* zs = cJSON_AddArrayToObject(j, "zones");
        for (int i = 0; i < tz_count; i++) {
            cJSON* z = cJSON_CreateObject();
            cJSON_AddStringToObject(z, "id", tz_zones[i].id);
            cJSON_AddStringToObject(z, "label", tz_zones[i].label);
            cJSON_AddItemToArray(zs, z);
        }
    }
    return send_json(r, j);
}

static esp_err_t api_settings(httpd_req_t* r) {
    cJSON* j = read_json(r);
    if (!j)
        return fail(r, "expected JSON");
    cJSON* b = cJSON_GetObjectItem(j, "brightness");
    if (cJSON_IsNumber(b))
        hub_set_brightness(b->valueint);
    const char* g = str_of(j, "game");
    if (g && strlen(g) < sizeof(hub_settings.game) && !strpbrk(g, " \r\n"))
        hub_set_game(g);
    const char* tz = str_of(j, "tz");
    if (tz)
        hub_set_tz(tz);
    cJSON_Delete(j);
    return ok(r);
}

static esp_err_t api_pair(httpd_req_t* r) {
    cJSON* j = read_json(r);
    if (!j)
        return fail(r, "expected JSON");
    bt_pair(cJSON_IsTrue(cJSON_GetObjectItem(j, "on")));
    cJSON_Delete(j);
    return ok(r);
}

static void close_phone(const uint8_t id[6]) {
    hub_lock();
    for (int i = 0; i < KNOWN_SLOTS; i++)
        if (phones[i].used && memcmp(phones[i].id, id, 6) == 0)
            httpd_sess_trigger_close(server, phones[i].fd);
    hub_unlock();
}

static esp_err_t api_controller(httpd_req_t* r) {
    cJSON* j = read_json(r);
    uint8_t id[6];
    const char* s = j ? str_of(j, "id") : NULL;
    if (!s || !known_id_parse(s, id)) {
        cJSON_Delete(j);
        return fail(r, "expected an id");
    }
    hub_lock();
    int i = known_find(&hub_known, id);
    link_kind_t kind = i >= 0 ? (link_kind_t)hub_known.k[i].kind : KIND_NONE;
    hub_unlock();
    if (i < 0) {
        cJSON_Delete(j);
        return fail(r, "no such controller");
    }
    cJSON* slot = cJSON_GetObjectItem(j, "slot");
    if (cJSON_IsTrue(cJSON_GetObjectItem(j, "forget"))) {
        if (kind == KIND_PHONE) {
            close_phone(id);
            hub_forget(id);
        } else {
            bt_forget(id);
        }
    } else if (cJSON_IsNumber(slot)) {
        hub_set_slot(id, slot->valueint);
    } else if (str_of(j, "grip")) {
        hub_set_grip(id, strcmp(str_of(j, "grip"), "sideways") == 0 ? GRIP_SIDEWAYS : GRIP_UPRIGHT);
    }
    cJSON_Delete(j);
    return ok(r);
}

static esp_err_t api_scan(httpd_req_t* r) {
    static net_seen_t seen[16];
    int n = net_scan(seen, 16);
    cJSON* a = cJSON_CreateArray();
    for (int i = 0; i < n; i++) {
        cJSON* o = cJSON_CreateObject();
        cJSON_AddStringToObject(o, "ssid", seen[i].ssid);
        cJSON_AddNumberToObject(o, "rssi", seen[i].rssi);
        cJSON_AddBoolToObject(o, "open", seen[i].open);
        cJSON_AddItemToArray(a, o);
    }
    return send_json(r, a);
}

static esp_err_t api_wifi(httpd_req_t* r) {
    cJSON* j = read_json(r);
    const char* ssid = j ? str_of(j, "ssid") : NULL;
    const char* pass = j ? str_of(j, "pass") : NULL;
    if (!ssid || !*ssid || strlen(ssid) > 32 || (pass && strlen(pass) > 64)) {
        cJSON_Delete(j);
        return fail(r, "a network name (up to 32 characters) and password (up to 64)");
    }
    hub_set_wifi(ssid, pass ? pass : "");
    cJSON_Delete(j);
    ok(r);
    net_restart_soon();
    return ESP_OK;
}

static esp_err_t api_wifi_forget(httpd_req_t* r) {
    ok(r);
    net_forget_wifi();
    return ESP_OK;
}

// ---- phones ----

static phone_t* phone_of(int fd) {
    for (int i = 0; i < KNOWN_SLOTS; i++)
        if (phones[i].used && phones[i].fd == fd)
            return &phones[i];
    return NULL;
}

typedef struct {
    int fd;
    char text[16];
} ws_out_t;

static void ws_send_work(void* arg) {
    ws_out_t* o = arg;
    httpd_ws_frame_t f = {.type = HTTPD_WS_TYPE_TEXT, .payload = (uint8_t*)o->text, .len = strlen(o->text)};
    httpd_ws_send_frame_async(server, o->fd, &f);
    free(o);
}

static void ws_send(int fd, const char* text) {
    ws_out_t* o = malloc(sizeof(ws_out_t));
    if (!o)
        return;
    o->fd = fd;
    strncpy(o->text, text, sizeof(o->text) - 1);
    o->text[sizeof(o->text) - 1] = 0;
    if (httpd_queue_work(server, ws_send_work, o) != ESP_OK)
        free(o);
}

void web_slots_changed(void) {
    if (!server)
        return;
    hub_lock();
    for (int i = 0; i < KNOWN_SLOTS; i++) {
        if (!phones[i].used)
            continue;
        char msg[16];
        int slot = known_live_slot(&hub_known, phones[i].id);
        snprintf(msg, sizeof(msg), slot ? "slot %d" : "full", slot);
        ws_send(phones[i].fd, msg);
    }
    hub_unlock();
}

static void phone_message(int fd, char* msg) {
    hub_lock();
    phone_t* p = phone_of(fd);
    if (p)
        p->last = hub_ms();
    if (strncmp(msg, "hello ", 6) == 0) {
        uint8_t id[6];
        if (p || !known_id_parse(msg + 6, id)) {
            hub_unlock();
            return;
        }
        for (int i = 0; i < KNOWN_SLOTS; i++) {
            if (phones[i].used && memcmp(phones[i].id, id, 6) == 0) {
                // the same phone again (its page reloaded) before its old socket was seen to close: the new one
                // takes over the slot, and the old one closes quietly instead of freeing it
                phones[i].used = false;
                httpd_sess_trigger_close(server, phones[i].fd);
            }
        }
        int slot = hub_connect(id, KIND_PHONE, "Phone");
        if (slot) {
            for (int i = 0; i < KNOWN_SLOTS; i++) {
                if (!phones[i].used) {
                    phones[i] = (phone_t){.used = true, .fd = fd, .last = hub_ms()};
                    memcpy(phones[i].id, id, 6);
                    break;
                }
            }
        }
        hub_unlock();
        char reply[16];
        snprintf(reply, sizeof(reply), slot ? "slot %d" : "full", slot);
        ws_send(fd, reply);
        return;
    }
    if (p && msg[0] == 's') {
        int dirs = 0, pick = 0, back = 0, menu = 0;                 // (a page from 1.0 sends no menu)
        if (sscanf(msg + 1, "%d %d %d %d", &dirs, &pick, &back, &menu) >= 3) {
            int slot = known_live_slot(&hub_known, p->id);
            pad_input_t in = {.dirs = (uint8_t)(dirs & 15), .pick = pick != 0, .back = back != 0, .menu = menu != 0};
            if (slot)
                hub_input(slot, &in);
        }
    }
    hub_unlock();
}

static esp_err_t ws_handler(httpd_req_t* r) {
    if (r->method == HTTP_GET)
        return ESP_OK;                                  // the handshake
    httpd_ws_frame_t f = {0};
    if (httpd_ws_recv_frame(r, &f, 0) != ESP_OK)
        return ESP_FAIL;
    if (f.type != HTTPD_WS_TYPE_TEXT || f.len == 0 || f.len > 64)
        return ESP_OK;
    char buf[65];
    f.payload = (uint8_t*)buf;
    if (httpd_ws_recv_frame(r, &f, f.len) != ESP_OK)
        return ESP_FAIL;
    buf[f.len] = 0;
    phone_message(httpd_req_to_sockfd(r), buf);
    return ESP_OK;
}

// A new connection when memory is short (a phone's burst of internet checks on the setup network) is turned away
// rather than starving Bluetooth; the phone tries again.
#define OPEN_NEEDS_BYTES 12000

static esp_err_t on_open(httpd_handle_t hd, int fd) {
    (void)hd;
    (void)fd;
    if (heap_caps_get_free_size(MALLOC_CAP_8BIT) < OPEN_NEEDS_BYTES) {
        ESP_LOGW(TAG, "memory short (%u bytes): turning a connection away",
                 (unsigned)heap_caps_get_free_size(MALLOC_CAP_8BIT));
        return ESP_FAIL;
    }
    return ESP_OK;
}

static void on_close(httpd_handle_t hd, int fd) {
    (void)hd;
    hub_lock();
    phone_t* p = phone_of(fd);
    if (p) {
        uint8_t id[6];
        memcpy(id, p->id, 6);
        p->used = false;
        hub_disconnect(id);
    }
    hub_unlock();
    close(fd);
}

void web_tick(uint32_t now) {
    static uint32_t next;
    if (!server || (int32_t)(now - next) < 0)
        return;
    next = now + 500;
    hub_lock();
    for (int i = 0; i < KNOWN_SLOTS; i++)
        if (phones[i].used && now - phones[i].last > PHONE_QUIET_MS) {
            ESP_LOGI(TAG, "a phone went quiet; letting it go");
            phones[i].last = now;                       // once: its close follows
            httpd_sess_trigger_close(server, phones[i].fd);
        }
    hub_unlock();
}

void web_start(void) {
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.max_uri_handlers = 16;
    cfg.max_open_sockets = 7;                       // lwIP has 12; the server keeps 3 for itself
    cfg.lru_purge_enable = true;
    cfg.stack_size = 6144;                          // (uses about 3 KB)
    cfg.open_fn = on_open;
    cfg.close_fn = on_close;
    if (httpd_start(&server, &cfg) != ESP_OK) {
        ESP_LOGE(TAG, "web server didn't start");
        return;
    }
    const httpd_uri_t uris[] = {
        {.uri = "/", .method = HTTP_GET, .handler = page_index},
        {.uri = "/pad", .method = HTTP_GET, .handler = page_pad},
        {.uri = "/favicon.ico", .method = HTTP_GET, .handler = no_content},
        {.uri = "/api/state", .method = HTTP_GET, .handler = api_state},
        {.uri = "/api/settings", .method = HTTP_POST, .handler = api_settings},
        {.uri = "/api/pair", .method = HTTP_POST, .handler = api_pair},
        {.uri = "/api/controller", .method = HTTP_POST, .handler = api_controller},
        {.uri = "/api/scan", .method = HTTP_GET, .handler = api_scan},
        {.uri = "/api/wifi", .method = HTTP_POST, .handler = api_wifi},
        {.uri = "/api/wifi_forget", .method = HTTP_POST, .handler = api_wifi_forget},
        {.uri = "/ws", .method = HTTP_GET, .handler = ws_handler, .is_websocket = true},
    };
    for (size_t i = 0; i < sizeof(uris) / sizeof(uris[0]); i++)
        httpd_register_uri_handler(server, &uris[i]);
    httpd_register_err_handler(server, HTTPD_404_NOT_FOUND, not_found);
}

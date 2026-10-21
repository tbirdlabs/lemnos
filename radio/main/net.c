#include "net.h"

#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "hub.h"
#include "lwip/sockets.h"
#include "mdns.h"

#define SETUP_AFTER_MS 20000           // no home network by then: open the setup network too
#define AP_CLOSE_AFTER_MS 60000        // on the home network: close the setup network after this
#define RETRY_MS 5000
#define RETRY_SETUP_MS 30000           // while the setup network is open, try less often (each try disturbs it)
#define HOSTNAME "salient"

static const char* TAG = "net";

static esp_netif_t* sta_if;
static volatile bool sta_up, ap_on, have_network;
static char ap_ssid[20];
static char ip[16];
static esp_timer_handle_t retry_timer, setup_timer, ap_close_timer, restart_timer;
static volatile bool dns_run;
static bool mdns_up;

// ---- captive portal DNS: every name is the radio ----

static void dns_task(void* arg) {
    (void)arg;
    int s = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in addr = {.sin_family = AF_INET, .sin_port = htons(53), .sin_addr.s_addr = htonl(INADDR_ANY)};
    struct timeval to = {.tv_sec = 0, .tv_usec = 500000};
    if (s < 0 || bind(s, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        ESP_LOGE(TAG, "captive DNS: no socket");
        if (s >= 0)
            close(s);
        vTaskDelete(NULL);
        return;
    }
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &to, sizeof(to));
    uint8_t buf[512];
    while (dns_run) {
        struct sockaddr_in from;
        socklen_t fl = sizeof(from);
        int n = recvfrom(s, buf, sizeof(buf), 0, (struct sockaddr*)&from, &fl);
        if (n < 12 || (buf[2] & 0x80) || ((buf[4] << 8) | buf[5]) < 1)
            continue;                                  // too short, a reply, or no question
        int p = 12;
        while (p < n && buf[p])
            p += buf[p] + 1;
        p++;
        if (p + 4 > n)
            continue;
        uint16_t qtype = (uint16_t)(buf[p] << 8 | buf[p + 1]);
        p += 4;                                        // the reply is the header, the first question, an answer
        buf[2] = 0x84 | (buf[2] & 0x01);               // a reply, authoritative, recursion as asked
        buf[3] = 0x80;
        buf[4] = 0;
        buf[5] = 1;
        memset(buf + 6, 0, 6);
        if (qtype == 1 && p + 16 <= (int)sizeof(buf)) {    // A: 192.168.4.1
            static const uint8_t ans[16] = {0xc0, 0x0c, 0, 1, 0, 1, 0, 0, 0, 60, 0, 4, 192, 168, 4, 1};
            memcpy(buf + p, ans, sizeof(ans));
            p += sizeof(ans);
            buf[7] = 1;
        }
        sendto(s, buf, p, 0, (struct sockaddr*)&from, fl);
    }
    close(s);
    vTaskDelete(NULL);
}

// ---- the setup network ----

static void start_ap(void) {
    if (ap_on)
        return;
    wifi_config_t ap = {0};
    strcpy((char*)ap.ap.ssid, ap_ssid);
    ap.ap.ssid_len = (uint8_t)strlen(ap_ssid);
    ap.ap.channel = 1;
    ap.ap.max_connection = 4;
    ap.ap.authmode = WIFI_AUTH_OPEN;
    esp_wifi_set_mode(WIFI_MODE_APSTA);
    esp_wifi_set_config(WIFI_IF_AP, &ap);
    ap_on = true;
    dns_run = true;
    xTaskCreate(dns_task, "dns", 2560, NULL, 3, NULL);
    ESP_LOGI(TAG, "setup network \"%s\" open: join it, then http://192.168.4.1/", ap_ssid);
}

static void stop_ap(void) {
    if (!ap_on)
        return;
    dns_run = false;
    ap_on = false;
    esp_wifi_set_mode(WIFI_MODE_STA);
    ESP_LOGI(TAG, "setup network closed");
}

static void on_setup_timer(void* arg) {
    (void)arg;
    if (!sta_up)
        start_ap();
}

static void on_ap_close(void* arg) {
    (void)arg;
    if (sta_up)
        stop_ap();
}

static void on_retry(void* arg) {
    (void)arg;
    if (have_network && !sta_up)
        esp_wifi_connect();
}

static void on_restart(void* arg) {
    (void)arg;
    esp_restart();
}

static void start_mdns(void) {
    if (mdns_up)
        return;
    if (mdns_init() != ESP_OK)
        return;
    mdns_hostname_set(HOSTNAME);
    mdns_instance_name_set("Salient board");
    mdns_service_add("Salient", "_http", "_tcp", 80, NULL, 0);
    mdns_up = true;
}

static void on_event(void* arg, esp_event_base_t base, int32_t id, void* data) {
    (void)arg;
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        if (have_network)
            esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        bool was = sta_up;
        sta_up = false;
        ip[0] = 0;
        if (was)
            ESP_LOGW(TAG, "lost the home network");
        if (have_network) {
            esp_timer_stop(retry_timer);
            esp_timer_start_once(retry_timer, (uint64_t)(ap_on ? RETRY_SETUP_MS : RETRY_MS) * 1000);
        }
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* e = data;
        snprintf(ip, sizeof(ip), IPSTR, IP2STR(&e->ip_info.ip));
        sta_up = true;
        ESP_LOGI(TAG, "on the home network: http://%s.local/ or http://%s/", HOSTNAME, ip);
        start_mdns();
        if (ap_on) {
            esp_timer_stop(ap_close_timer);
            esp_timer_start_once(ap_close_timer, (uint64_t)AP_CLOSE_AFTER_MS * 1000);
        }
    }
}

void net_start(void) {
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    sta_if = esp_netif_create_default_wifi_sta();
    esp_netif_create_default_wifi_ap();
    esp_netif_set_hostname(sta_if, HOSTNAME);

    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_SOFTAP);
    snprintf(ap_ssid, sizeof(ap_ssid), "Salient-%02X%02X", mac[4], mac[5]);

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    esp_wifi_set_storage(WIFI_STORAGE_RAM);         // the radio keeps the network in its own settings
    esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, on_event, NULL);
    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, on_event, NULL);

    const esp_timer_create_args_t t1 = {.callback = on_retry, .name = "wifi retry"};
    const esp_timer_create_args_t t2 = {.callback = on_setup_timer, .name = "wifi setup"};
    const esp_timer_create_args_t t3 = {.callback = on_ap_close, .name = "ap close"};
    const esp_timer_create_args_t t4 = {.callback = on_restart, .name = "restart"};
    esp_timer_create(&t1, &retry_timer);
    esp_timer_create(&t2, &setup_timer);
    esp_timer_create(&t3, &ap_close_timer);
    esp_timer_create(&t4, &restart_timer);

    wifi_config_t sta = {0};
    hub_lock();
    have_network = hub_settings.ssid[0] != 0;
    strncpy((char*)sta.sta.ssid, hub_settings.ssid, sizeof(sta.sta.ssid));
    strncpy((char*)sta.sta.password, hub_settings.pass, sizeof(sta.sta.password));
    hub_unlock();
    sta.sta.threshold.authmode = WIFI_AUTH_OPEN;
    sta.sta.scan_method = WIFI_ALL_CHANNEL_SCAN;
    sta.sta.sort_method = WIFI_CONNECT_AP_BY_SIGNAL;

    if (have_network) {
        esp_wifi_set_mode(WIFI_MODE_STA);
        esp_wifi_set_config(WIFI_IF_STA, &sta);
        esp_wifi_start();
        esp_timer_start_once(setup_timer, (uint64_t)SETUP_AFTER_MS * 1000);
        ESP_LOGI(TAG, "joining \"%s\"", (char*)sta.sta.ssid);
    } else {
        esp_wifi_set_mode(WIFI_MODE_APSTA);
        esp_wifi_start();
        start_ap();
    }
    // Bluetooth shares the radio: WiFi's modem sleep must stay on for coexistence (the default, WIFI_PS_MIN_MODEM)
}

void net_status(net_status_t* s) {
    memset(s, 0, sizeof(*s));
    s->connected = sta_up;
    s->ap_on = ap_on;
    strcpy(s->ap_ssid, ap_ssid);
    strcpy(s->ip, ip);
    hub_lock();
    strncpy(s->ssid, hub_settings.ssid, sizeof(s->ssid) - 1);
    hub_unlock();
    wifi_ap_record_t r;
    if (sta_up && esp_wifi_sta_get_ap_info(&r) == ESP_OK)
        s->rssi = r.rssi;
}

int net_scan(net_seen_t* out, int max) {
    wifi_scan_config_t sc = {0};
    if (esp_wifi_scan_start(&sc, true) != ESP_OK)
        return 0;
    uint16_t n = 20;
    static wifi_ap_record_t recs[20];
    if (esp_wifi_scan_get_ap_records(&n, recs) != ESP_OK)
        return 0;
    int k = 0;
    for (int i = 0; i < n && k < max; i++) {        // already strongest first; skip hidden and repeats
        if (!recs[i].ssid[0])
            continue;
        bool dup = false;
        for (int j = 0; j < k; j++)
            if (strcmp(out[j].ssid, (char*)recs[i].ssid) == 0)
                dup = true;
        if (dup)
            continue;
        strncpy(out[k].ssid, (char*)recs[i].ssid, sizeof(out[k].ssid) - 1);
        out[k].ssid[sizeof(out[k].ssid) - 1] = 0;
        out[k].rssi = recs[i].rssi;
        out[k].open = recs[i].authmode == WIFI_AUTH_OPEN;
        k++;
    }
    return k;
}

void net_restart_soon(void) {
    esp_timer_stop(restart_timer);
    esp_timer_start_once(restart_timer, 1500 * 1000);
}

void net_forget_wifi(void) {
    hub_set_wifi("", "");
    net_restart_soon();
}

bool net_ap_active(void) {
    return ap_on;
}

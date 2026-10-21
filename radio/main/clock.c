#include "clock.h"

#include <sys/time.h>

#include "esp_log.h"
#include "esp_netif_sntp.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "hub.h"
#include "tz.h"

static const char* TAG = "clock";
static volatile bool synced, faked, send_flag;

void clock_send_now(void) {
    send_flag = true;
}

static void on_sync(struct timeval* tv) {
    (void)tv;
    if (!synced)
        ESP_LOGI(TAG, "NTP set the clock");
    synced = true;
    send_flag = true;
}

static void ntp_start(void) {
    esp_sntp_config_t c = ESP_NETIF_SNTP_DEFAULT_CONFIG("pool.ntp.org");
    c.sync_cb = on_sync;
    esp_netif_sntp_init(&c);                     // keeps trying until the network is up, then every hour
}

static const char* rule(void) {
    hub_lock();
    const char* r = hub_tz_rule();
    hub_unlock();
    return r;
}

bool clock_local(int64_t* local, bool* dst) {
    if (!synced && !faked)
        return false;
    struct timeval tv;
    gettimeofday(&tv, NULL);
    *local = tv.tv_sec + tz_offset(rule(), tv.tv_sec, dst);
    return true;
}

const char* clock_source(void) {
    return faked ? "fake" : synced ? "ntp" : "none";
}

void clock_fake(int64_t utc) {
    if (!faked)
        esp_netif_sntp_deinit();
    faked = true;
    struct timeval tv = {.tv_sec = (time_t)utc, .tv_usec = 0};
    settimeofday(&tv, NULL);
    send_flag = true;
    ESP_LOGI(TAG, "clock set by hand; NTP off until 'ntp'");
}

void clock_ntp(void) {
    if (!faked)
        return;
    faked = false;
    synced = false;
    ntp_start();
}

static void clock_task(void* arg) {
    (void)arg;
    int32_t last_off = INT32_MIN;
    for (;;) {
        struct timeval tv;
        gettimeofday(&tv, NULL);
        vTaskDelay(pdMS_TO_TICKS(1000 - tv.tv_usec / 1000 + 2));    // just past the next second
        if (!synced && !faked)
            continue;
        gettimeofday(&tv, NULL);
        int64_t t = tv.tv_sec;
        int32_t off = tz_offset(rule(), t, NULL);
        int64_t local = t + off;
        if (!send_flag && off == last_off && local % 60 != 0)
            continue;
        send_flag = false;
        last_off = off;
        int y, mo, d, h, mi, s;
        tz_civil(local, &y, &mo, &d, &h, &mi, &s);
        char l[LINK_LINE_MAX + 2];
        link_fmt_time(l, y, mo, d, h, mi, s);
        hub_send(l);
    }
}

void clock_start(void) {
    ntp_start();
    xTaskCreate(clock_task, "clock", 3584, NULL, 4, NULL);   // room for printf: "link on" echoes what it sends
}

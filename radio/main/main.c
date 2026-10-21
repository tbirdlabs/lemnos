// The Salient radio co-processor: Bluetooth controllers, WiFi (web settings, phone controller, NTP time), and a UART
// link to the SCORPIO that carries it all as text lines (core/link.h, NOTES.md). See README.md.

#include <btstack_port_esp32.h>
#include <btstack_run_loop.h>
#include <btstack_stdio_esp32.h>
#include <uni.h>

#include "bt.h"
#include "clock.h"
#include "console.h"
#include "display.h"
#include "hub.h"
#include "net.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "sdkconfig.h"
#include "store.h"
#include "web.h"

#ifndef CONFIG_BLUEPAD32_PLATFORM_CUSTOM
#error "Needs CONFIG_BLUEPAD32_PLATFORM_CUSTOM (sdkconfig.defaults)"
#endif

// Free memory after each part starts (the radio runs Bluetooth Classic, BLE and WiFi at once on 320 KB)
static void heap(const char* after) {
    ESP_LOGI("heap", "after %s: %u free, largest block %u", after, (unsigned)heap_caps_get_free_size(MALLOC_CAP_8BIT),
             (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_8BIT));
}

int app_main(void) {
#if defined(CONFIG_ESP_CONSOLE_UART) && !defined(CONFIG_BLUEPAD32_USB_CONSOLE_ENABLE)
    btstack_stdio_init();
#endif
    store_init();
    hub_init();                        // settings, known controllers, the UART link
    heap("hub");
    display_start();
    heap("display");
    net_start();                       // WiFi, the setup network, mDNS
    heap("WiFi");
    web_start();
    heap("web");
    clock_start();                     // NTP, TIME lines
    heap("clock");

    btstack_init();
    uni_platform_set_custom(bt_platform());
    uni_init(0, NULL);                 // starts Bluepad32's console too
    console_start();
    heap("Bluetooth");
    btstack_run_loop_execute();        // Bluetooth runs on this task from here on
    return 0;
}

// What shared/ needs from the platform: logging and a short critical section. ESP32 (ESP-IDF, FreeRTOS) or
// Pico W (Pico SDK; Bluetooth and the hub all run on BTstack's run loop there).
#pragma once

#if defined(ESP_PLATFORM)

#include "esp_log.h"
#include "freertos/FreeRTOS.h"

#define LOGI(tag, ...) ESP_LOGI(tag, __VA_ARGS__)
#define LOGW(tag, ...) ESP_LOGW(tag, __VA_ARGS__)
typedef portMUX_TYPE port_mux_t;
#define PORT_MUX_INIT portMUX_INITIALIZER_UNLOCKED
#define port_enter(m) taskENTER_CRITICAL(m)
#define port_exit(m) taskEXIT_CRITICAL(m)

#else

#include <stdio.h>

#define LOGI(tag, fmt, ...) printf("I %s: " fmt "\n", tag, ##__VA_ARGS__)
#define LOGW(tag, fmt, ...) printf("W %s: " fmt "\n", tag, ##__VA_ARGS__)
typedef int port_mux_t;                // one thread of control (BTstack's run loop): nothing to guard
#define PORT_MUX_INIT 0
#define port_enter(m) ((void)(m))
#define port_exit(m) ((void)(m))

#endif

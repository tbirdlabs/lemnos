// Bluepad32's settings for the Pico W build (what menuconfig sets on the ESP32; sdkconfig.defaults there).
#pragma once

#define CONFIG_BLUEPAD32_MAX_DEVICES 4
#define CONFIG_BLUEPAD32_MAX_ALLOWLIST 8
#define CONFIG_BLUEPAD32_GAP_SECURITY 1
#define CONFIG_BLUEPAD32_ENABLE_BLE_BY_DEFAULT 1
#define CONFIG_BLUEPAD32_PLATFORM_CUSTOM
#define CONFIG_TARGET_PICO_W
#define CONFIG_BLUEPAD32_LOG_LEVEL 2           // info

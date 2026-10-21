# mdns comes from the ESP-IDF component registry (idf_component.yml beside this file). PlatformIO only
# reconfigures when a CMakeLists.txt or sdkconfig changes, so after editing idf_component.yml, save this file too.
idf_component_register(SRCS "main.c" "hub.c" "store.c" "net.c" "web.c" "clock.c" "buttons.c" "display.c"
                            "console.c" "../shared/bt.c"
                       INCLUDE_DIRS "." "../shared"
                       REQUIRES bluepad32 btstack core nvs_flash esp_wifi esp_netif esp_event esp_http_server
                                esp_timer esp_driver_uart esp_driver_gpio esp_driver_spi esp_lcd json console
                       EMBED_TXTFILES "../web/index.html" "../web/pad.html")

# The board (platformio.ini: board_build.cmake_extra_args = -DRADIO_BOARD=...), for board.h
if(NOT RADIO_BOARD)
    set(RADIO_BOARD esp32dev)
endif()
target_compile_definitions(${COMPONENT_LIB} PRIVATE RADIO_BOARD_${RADIO_BOARD}=1)

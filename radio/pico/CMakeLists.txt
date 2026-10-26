# The Lemnos radio on a Pico W or Pico 2 W (experimental): Bluetooth controllers to the SCORPIO over the same UART
# protocol as the ESP32 build, from the same core/ and shared/ code. No WiFi yet. See README.md.
#
#   cmake -B build -G Ninja -DPICO_SDK_PATH=... [-DPICO_BOARD=pico2_w] [-DRADIO_UART_TX=4 -DRADIO_UART_RX=5]
#   cmake --build build                  -> build/lemnos_radio.uf2
cmake_minimum_required(VERSION 3.13)

if(NOT DEFINED PICO_BOARD)
    set(PICO_BOARD pico_w)
endif()

set(RADIO ${CMAKE_CURRENT_LIST_DIR}/..)
set(RADIO_UART_TX 4 CACHE STRING "GPIO to the SCORPIO's RX (UART1 TX: 4, 8 or 20)")
set(RADIO_UART_RX 5 CACHE STRING "GPIO from the SCORPIO's TX (UART1 RX: 5, 9 or 21)")

# Bluepad32 4.2.0, as tools/get_bluepad32.py fetches it (its BTstack comes from the Pico SDK here)
if(DEFINED ENV{LEMNOS_RADIO_DEPS})
    set(RADIO_DEPS $ENV{LEMNOS_RADIO_DEPS})
elseif(CMAKE_HOST_WIN32)
    file(TO_CMAKE_PATH "$ENV{USERPROFILE}/.lemnos-radio" RADIO_DEPS)
else()
    set(RADIO_DEPS $ENV{HOME}/.lemnos-radio)
endif()
set(BLUEPAD32_ROOT ${RADIO_DEPS}/bluepad32-4.2.0/src)
if(NOT EXISTS ${BLUEPAD32_ROOT}/src/components/bluepad32)
    message(FATAL_ERROR "Bluepad32 isn't set up: run  python ../tools/get_bluepad32.py  first")
endif()

include(pico_sdk_import.cmake)
project(lemnos_radio C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()
set(BTSTACK_ROOT ${PICO_SDK_PATH}/lib/btstack)

add_executable(lemnos_radio
    main.c
    ${RADIO}/shared/bt.c
    ${RADIO}/core/link.c
    ${RADIO}/core/pads.c
    ${RADIO}/core/known.c
)
target_include_directories(lemnos_radio PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}
    ${RADIO}/shared
    ${RADIO}/core
    ${BLUEPAD32_ROOT}/src/components/bluepad32/include)
target_compile_definitions(lemnos_radio PRIVATE RADIO_UART_TX=${RADIO_UART_TX} RADIO_UART_RX=${RADIO_UART_RX})

# btstack_config.h and sdkconfig.h, for Bluepad32 too
include_directories(${CMAKE_CURRENT_LIST_DIR})
include_directories(${BTSTACK_ROOT}/3rd-party/bluedroid/encoder/include)
include_directories(${BTSTACK_ROOT}/3rd-party/bluedroid/decoder/include)
include_directories(${BTSTACK_ROOT}/src)

target_link_libraries(lemnos_radio PUBLIC
    pico_stdlib
    hardware_uart
    pico_cyw43_arch_none
    pico_btstack_classic
    pico_btstack_ble
    pico_btstack_cyw43
    bluepad32)
add_subdirectory(${BLUEPAD32_ROOT}/src/components/bluepad32 libbluepad32)

pico_enable_stdio_usb(lemnos_radio 1)
pico_enable_stdio_uart(lemnos_radio 0)
pico_add_extra_outputs(lemnos_radio)

# The Lemnos radio co-processor (ESP-IDF project; PlatformIO builds it through platformio.ini).
cmake_minimum_required(VERSION 3.16)

# Bluepad32 and BTstack, set up by tools/get_bluepad32.py outside the source tree
set(BLUEPAD32_VERSION 4.2.0)
if(DEFINED ENV{LEMNOS_RADIO_DEPS})
    set(RADIO_DEPS $ENV{LEMNOS_RADIO_DEPS})
elseif(CMAKE_HOST_WIN32)
    file(TO_CMAKE_PATH "$ENV{USERPROFILE}/.lemnos-radio" RADIO_DEPS)
else()
    set(RADIO_DEPS $ENV{HOME}/.lemnos-radio)
endif()
set(BP32_COMPONENTS ${RADIO_DEPS}/bluepad32-${BLUEPAD32_VERSION}/components)
if(NOT EXISTS ${BP32_COMPONENTS}/bluepad32)
    message(FATAL_ERROR "Bluepad32 isn't set up: run  python tools/get_bluepad32.py  first (looked in ${BP32_COMPONENTS})")
endif()
set(EXTRA_COMPONENT_DIRS ${BP32_COMPONENTS} ${CMAKE_CURRENT_LIST_DIR}/core)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(lemnos_radio)

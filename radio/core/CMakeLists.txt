# Portable C shared by every radio build (ESP32, Pico W) and the desktop tests (test/run_tests.py):
# no platform headers here.
set(CORE_SRCS link.c pads.c known.c tz.c)
if(IDF_TARGET)
    idf_component_register(SRCS ${CORE_SRCS} INCLUDE_DIRS ".")
else()
    add_library(radio_core STATIC ${CORE_SRCS})
    target_include_directories(radio_core PUBLIC ${CMAKE_CURRENT_LIST_DIR})
endif()

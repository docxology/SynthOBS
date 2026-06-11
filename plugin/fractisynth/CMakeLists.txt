# FractiSynth — native OBS Studio plugin (libobs filter module).
#
# Follows the obs-studio in-tree plugin CMake convention. Build standalone with
# the OBS plugin template, or drop into obs-studio/plugins/ and add to the
# plugins CMakeLists.
#
#   cmake -B build -DCMAKE_BUILD_TYPE=Release
#   cmake --build build
#
# Requires: libobs dev headers (OBS::libobs) and, for live telemetry, libcurl.

cmake_minimum_required(VERSION 3.16...3.28)

project(fractisynth VERSION 1.618.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# --- libobs ----------------------------------------------------------------
# In-tree builds provide the OBS::libobs target. Standalone builds locate it
# via the OBS plugin SDK (libobs CONFIG package).
if(NOT TARGET OBS::libobs)
  find_package(libobs REQUIRED)
endif()

add_library(${PROJECT_NAME} MODULE)

target_sources(${PROJECT_NAME} PRIVATE src/fractisynth.c)
target_include_directories(${PROJECT_NAME} PRIVATE src)
target_link_libraries(${PROJECT_NAME} PRIVATE OBS::libobs)

# --- libcurl (live NOAA SWPC telemetry; optional) --------------------------
find_package(CURL)
if(CURL_FOUND)
  target_compile_definitions(${PROJECT_NAME} PRIVATE HAVE_CURL)
  target_link_libraries(${PROJECT_NAME} PRIVATE CURL::libcurl)
  message(STATUS "FractiSynth: libcurl found — live SWO telemetry thread enabled")
else()
  message(WARNING "FractiSynth: libcurl NOT found — SWO runs on the default vector")
endif()

# math (tanhf/isfinite) on Unix
if(UNIX AND NOT APPLE)
  target_link_libraries(${PROJECT_NAME} PRIVATE m)
endif()

set_target_properties(${PROJECT_NAME} PROPERTIES PREFIX "")

# Install into the OBS plugins directory (overridden by the OBS plugin template).
if(DEFINED OBS_PLUGIN_DESTINATION)
  install(TARGETS ${PROJECT_NAME} LIBRARY DESTINATION "${OBS_PLUGIN_DESTINATION}")
endif()

# Locale data
install(DIRECTORY data/ DESTINATION "${CMAKE_INSTALL_PREFIX}/data/obs-plugins/${PROJECT_NAME}")

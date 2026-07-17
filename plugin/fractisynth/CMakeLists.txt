# FractiSynth — native OBS Studio plugin (libobs filter module).
#
# Follows the obs-studio in-tree plugin CMake convention. Build standalone with
# the OBS plugin template, or drop into obs-studio/plugins/ and add to the
# plugins CMakeLists.
#
#   cmake -B build -DCMAKE_BUILD_TYPE=Release -DOBS_ROOT=/path/to/OBS.app/Contents
#   cmake --build build
#
# Requires: libobs dev headers (OBS::libobs) and libcurl.

cmake_minimum_required(VERSION 3.16...3.28)

project(fractisynth VERSION 1.618.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

option(FRACTISYNTH_REQUIRE_CURL "Require libcurl-backed live NOAA telemetry" ON)
set(OBS_ROOT "" CACHE PATH "OBS installation or SDK root containing libobs CMake package")
set(FRACTISYNTH_OBS_SDK_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.obs-sdk/obs-studio" CACHE PATH "OBS source/header checkout used when OBS_ROOT points at an installed macOS OBS.app")
set(FRACTISYNTH_SIMDE_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.obs-sdk/simde" CACHE PATH "SIMDe header checkout used by OBS headers")

if(OBS_ROOT)
  list(APPEND CMAKE_PREFIX_PATH
    "${OBS_ROOT}"
    "${OBS_ROOT}/cmake"
    "${OBS_ROOT}/lib/cmake"
    "${OBS_ROOT}/Frameworks"
    "${OBS_ROOT}/Resources"
  )
endif()

# --- libobs ----------------------------------------------------------------
# In-tree builds provide the OBS::libobs target. Standalone builds locate it
# via the OBS plugin SDK (libobs CONFIG package), or on macOS via OBS.app's
# libobs.framework plus the matching headers fetched by build.sh.
if(NOT TARGET OBS::libobs)
  if(APPLE
      AND OBS_ROOT
      AND EXISTS "${OBS_ROOT}/Frameworks/libobs.framework"
      AND EXISTS "${FRACTISYNTH_OBS_SDK_ROOT}/libobs/obs-module.h")
    add_library(OBS::libobs INTERFACE IMPORTED)
    target_include_directories(OBS::libobs INTERFACE
      "${FRACTISYNTH_OBS_SDK_ROOT}/libobs"
      "${FRACTISYNTH_SIMDE_ROOT}"
    )
    target_link_libraries(OBS::libobs INTERFACE
      "-F${OBS_ROOT}/Frameworks"
      "-framework libobs"
      "-Wl,-rpath,${OBS_ROOT}/Frameworks"
    )
    message(STATUS "FractiSynth: using OBS.app libobs.framework with local SDK headers")
  else()
    find_package(libobs REQUIRED)
  endif()
endif()

add_library(${PROJECT_NAME} MODULE)

target_sources(${PROJECT_NAME} PRIVATE src/fractisynth.c)
target_include_directories(${PROJECT_NAME} PRIVATE src)
target_link_libraries(${PROJECT_NAME} PRIVATE OBS::libobs)

# --- libcurl (live NOAA SWPC telemetry; optional) --------------------------
if(FRACTISYNTH_REQUIRE_CURL)
  find_package(CURL REQUIRED)
else()
  find_package(CURL)
endif()
if(CURL_FOUND)
  target_compile_definitions(${PROJECT_NAME} PRIVATE HAVE_CURL)
  target_link_libraries(${PROJECT_NAME} PRIVATE CURL::libcurl)
  message(STATUS "FractiSynth: libcurl found — live SWO telemetry thread enabled")
else()
  message(WARNING "FractiSynth: libcurl NOT found — live SWO telemetry disabled by explicit configuration")
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

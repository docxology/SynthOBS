#!/usr/bin/env bash
#
# Build the FractiSynth OBS plugin against the installed OBS Studio (macOS).
#
# Verified path: links directly against /Applications/OBS.app's libobs.framework
# using the matching libobs C headers (cloned at the installed OBS tag). Produces a
# loadable `FractiSynth.plugin` bundle, ad-hoc signs it, and (with --install) drops
# it into the user OBS plugins directory.
#
#   ./build.sh            # build + sign → build/FractiSynth.plugin
#   ./build.sh --install  # also install into ~/Library/Application Support/obs-studio/plugins
#
# Requires: clang, git, an installed OBS.app, and libcurl for live telemetry.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

OBS_APP="${OBS_APP:-/Applications/OBS.app}"
FW="$OBS_APP/Contents/Frameworks"
SDK_DIR="$HERE/.obs-sdk"
OBS_SRC="$SDK_DIR/obs-studio"
SIMDE_DIR="$SDK_DIR/simde"
BUILD="$HERE/build"
PLUGIN_NAME="fractisynth"
BUNDLE="$BUILD/FractiSynth.plugin"

if [[ ! -d "$OBS_APP" ]]; then
	echo "ERROR: OBS.app not found at $OBS_APP (set OBS_APP=...)." >&2
	exit 1
fi

# Resolve the installed OBS version so headers match the ABI exactly.
OBS_VER="$(defaults read "$OBS_APP/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || echo 32.1.2)"
echo "==> Target OBS Studio: $OBS_VER"

# --- 1. libobs C headers (matching tag) -----------------------------------
if [[ ! -f "$OBS_SRC/libobs/obs-module.h" ]]; then
	echo "==> Fetching libobs headers @ $OBS_VER"
	rm -rf "$OBS_SRC"
	git clone --depth 1 --branch "$OBS_VER" --filter=blob:none --sparse \
		https://github.com/obsproject/obs-studio.git "$OBS_SRC"
	git -C "$OBS_SRC" sparse-checkout set libobs frontend/api
fi
if [[ ! -f "$SIMDE_DIR/simde/x86/sse2.h" ]]; then
	echo "==> Fetching SIMDe (header-only)"
	rm -rf "$SIMDE_DIR"
	git clone --depth 1 https://github.com/simd-everywhere/simde.git "$SIMDE_DIR"
fi
# Minimal generated config header (normally produced by OBS's CMake).
if [[ ! -f "$OBS_SRC/libobs/obsconfig.h" ]]; then
	cat > "$OBS_SRC/libobs/obsconfig.h" <<'CFG'
#pragma once
#define OBS_DATA_PATH "../../data"
#define OBS_PLUGIN_PATH "../../obs-plugins/%module%"
#define OBS_PLUGIN_DESTINATION "obs-plugins"
#define OBS_RELEASE_CANDIDATE 0
#define OBS_BETA 0
CFG
fi

SDKROOT="$(xcrun --show-sdk-path)"
CURL_FLAGS=""
CURL_LIB=""
if echo '#include <curl/curl.h>' | clang -fsyntax-only -xc - -I"$SDKROOT/usr/include" 2>/dev/null; then
	CURL_FLAGS="-DHAVE_CURL"
	CURL_LIB="-lcurl"
	echo "==> libcurl found — live SWO telemetry thread enabled"
else
	echo "ERROR: libcurl headers not found; live NOAA telemetry is required for release builds." >&2
	exit 1
fi

# --- 2. compile + link ----------------------------------------------------
mkdir -p "$BUILD"
echo "==> Compiling $PLUGIN_NAME.c"
clang -c src/fractisynth.c -o "$BUILD/$PLUGIN_NAME.o" \
	-I"$OBS_SRC/libobs" -I"$SIMDE_DIR" -I"$SDKROOT/usr/include" \
	$CURL_FLAGS -fPIC -std=gnu11 -O2 -Wall

# --- 2b. OPTIONAL Qt6 frontend dock (purely additive; never fails the build) -
# Compiled only when Qt6 + the obs-frontend-api header are present. A failure
# here is swallowed — the core plugin (filters + console source) still ships.
DOCK_OBJ=""
DOCK_LIBS=""
# Prefer a bundled Qt whose version matches OBS's runtime Qt (e.g. obs-deps Qt
# 6.8.x dropped into .obs-sdk/qt-6.8) so the frontend dock can actually load; the
# version gate below still guards it. Falls back to Homebrew Qt otherwise.
if [[ -z "${QT_PREFIX:-}" && -d "$SDK_DIR/qt-6.8/lib/QtWidgets.framework" ]]; then
	QT_PREFIX="$SDK_DIR/qt-6.8"
fi
QT_PREFIX="${QT_PREFIX:-$(brew --prefix qt6 2>/dev/null || echo /opt/homebrew/opt/qt6)}"
FRONTEND_API="$OBS_SRC/frontend/api"

# CRITICAL: the dock must be built against headers whose Qt MAJOR.MINOR matches
# OBS's bundled runtime Qt. A newer-minor header set (e.g. 6.11 vs OBS 6.8) inlines
# QAnyStringView/doSetPen/version-tag symbols ABSENT from the runtime, so the module
# fails to dlopen ENTIRELY — strictly worse than no dock. We therefore compile the
# dock ONLY on an exact major.minor match. Point QT_PREFIX at a Qt 6.8.x install
# (e.g. the obs-deps Qt) to enable it.
_qt_ver() { # echo MAJOR.MINOR from a Qt prefix's qtcoreversion.h, or empty
	local hdr="$1/lib/QtCore.framework/Headers/qtcoreversion.h"
	[[ -f "$hdr" ]] || hdr="$1/include/QtCore/qtcoreversion.h"
	[[ -f "$hdr" ]] || return 0
	grep -oE 'QTCORE_VERSION_STR "[0-9]+\.[0-9]+' "$hdr" 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1
}
# `|| true` so a no-match grep under `set -euo pipefail` yields empty (skip dock)
# rather than aborting the whole build.
OBS_QT_MM="$(otool -L "$FW/QtCore.framework/Versions/A/QtCore" 2>/dev/null | grep -oE 'current version [0-9]+\.[0-9]+' | grep -oE '[0-9]+\.[0-9]+' | head -1 || true)"
[[ -z "$OBS_QT_MM" ]] && OBS_QT_MM="$(otool -L /Applications/OBS.app/Contents/Frameworks/QtCore.framework/Versions/A/QtCore 2>/dev/null | grep -oE '\(compatibility.*current version [0-9]+\.[0-9]+' | grep -oE '[0-9]+\.[0-9]+$' | head -1 || true)"
QT_PREFIX_MM="$(_qt_ver "$QT_PREFIX" || true)"

if [[ "${FRACTISYNTH_NO_DOCK:-0}" != "1" && -f "$FRONTEND_API/obs-frontend-api.h" \
	&& -d "$FW/QtWidgets.framework" && -n "$QT_PREFIX_MM" && -n "$OBS_QT_MM" \
	&& "$QT_PREFIX_MM" == "$OBS_QT_MM" ]]; then
	echo "==> Qt6 $QT_PREFIX_MM matches OBS runtime $OBS_QT_MM ($QT_PREFIX) — compiling optional frontend dock"
	# brew Qt6 is framework-style (lib/*.framework/Headers); support both layouts.
	if [[ -d "$QT_PREFIX/include/QtWidgets" ]]; then
		QT_INC=(-I"$QT_PREFIX/include" -I"$QT_PREFIX/include/QtWidgets"
			-I"$QT_PREFIX/include/QtGui" -I"$QT_PREFIX/include/QtCore")
	else
		QT_INC=(-F"$QT_PREFIX/lib"
			-I"$QT_PREFIX/lib/QtWidgets.framework/Headers"
			-I"$QT_PREFIX/lib/QtGui.framework/Headers"
			-I"$QT_PREFIX/lib/QtCore.framework/Headers")
	fi
	# QT_NO_VERSION_TAGGING: do NOT emit the _qt_version_tag_6_NN symbol. Without
	# this, a plugin compiled against (e.g.) Qt 6.11 headers requires a version
	# symbol absent in OBS's bundled Qt 6.8 and fails to dlopen ENTIRELY — taking
	# the whole module (filters + source included) down. With it, the dock links
	# against OBS's own runtime Qt via @rpath and resolves only stable 6.0 symbols.
	if clang++ -c src/fractisynth_dock.cpp -o "$BUILD/fractisynth_dock.o" \
		-I"$OBS_SRC/libobs" -I"$SIMDE_DIR" -I"$SDKROOT/usr/include" \
		-I"$FRONTEND_API" "${QT_INC[@]}" \
		-DQT_NO_VERSION_TAGGING \
		-fPIC -std=c++17 -O2 -fvisibility=hidden \
		-Wno-deprecated-declarations \
		-Wno-error=implicit-function-declaration \
		2>"$BUILD/dock_compile.log"; then
		DOCK_OBJ="$BUILD/fractisynth_dock.o"
		# Link against OBS's OWN Qt frameworks (runtime ABI) + frontend api.
		DOCK_LIBS="-framework QtWidgets -framework QtGui -framework QtCore $FW/obs-frontend-api.dylib"
		echo "    dock compiled ✓"
	else
		echo "    dock compile FAILED (see $BUILD/dock_compile.log) — shipping core plugin without it"
		head -5 "$BUILD/dock_compile.log" || true
	fi
elif [[ -n "$QT_PREFIX_MM" && -n "$OBS_QT_MM" && "$QT_PREFIX_MM" != "$OBS_QT_MM" ]]; then
	echo "==> Qt $QT_PREFIX_MM ≠ OBS runtime Qt $OBS_QT_MM — SKIPPING dock to protect the plugin"
	echo "    (point QT_PREFIX at a Qt $OBS_QT_MM install — e.g. obs-deps Qt — to enable the frontend dock)"
else
	echo "==> Qt6/frontend-api not available — building core plugin (no dock)"
fi

echo "==> Linking bundle"
clang++ -bundle "$BUILD/$PLUGIN_NAME.o" $DOCK_OBJ -o "$BUILD/$PLUGIN_NAME" \
	-F"$FW" -framework libobs $CURL_LIB $DOCK_LIBS \
	-Wl,-undefined,dynamic_lookup

# --- 3. assemble the .plugin bundle ---------------------------------------
echo "==> Assembling $BUNDLE"
rm -rf "$BUNDLE"
mkdir -p "$BUNDLE/Contents/MacOS" "$BUNDLE/Contents/Resources"
mv "$BUILD/$PLUGIN_NAME" "$BUNDLE/Contents/MacOS/FractiSynth"
cp -R data/locale "$BUNDLE/Contents/Resources/"
cp data/*.effect "$BUNDLE/Contents/Resources/"
cat > "$BUNDLE/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleDevelopmentRegion</key><string>en</string>
	<key>CFBundleExecutable</key><string>FractiSynth</string>
	<key>CFBundleIdentifier</key><string>institute.activeinference.fractisynth</string>
	<key>CFBundleName</key><string>FractiSynth</string>
	<key>CFBundlePackageType</key><string>BNDL</string>
	<key>CFBundleShortVersionString</key><string>1.618.0</string>
	<key>CFBundleVersion</key><string>1.618.0</string>
	<key>LSMinimumSystemVersion</key><string>11.0</string>
</dict>
</plist>
PLIST

# --- 4. ad-hoc sign (lets a hardened OBS load a local dev plugin) ----------
echo "==> Ad-hoc signing"
codesign --force --deep --sign - "$BUNDLE" >/dev/null 2>&1 || \
	echo "   (codesign skipped/failed — plugin may need manual signing)"

echo "==> Built: $BUNDLE"
file "$BUNDLE/Contents/MacOS/FractiSynth"

# --- 5. optional install --------------------------------------------------
if [[ "${1:-}" == "--install" ]]; then
	DEST="$HOME/Library/Application Support/obs-studio/plugins"
	mkdir -p "$DEST"
	rm -rf "$DEST/FractiSynth.plugin"
	cp -R "$BUNDLE" "$DEST/"
	echo "==> Installed to $DEST/FractiSynth.plugin"
	echo "    Restart OBS; add the 'FractiSynth — φ Video Calibration' or"
	echo "    '… φ Harmonic Limiter' filter to a source."
fi

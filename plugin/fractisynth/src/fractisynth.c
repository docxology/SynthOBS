/*
 * FractiSynth — the native transducer core for SynthOBS (v1.618).
 *
 * A libobs plugin exposing two filters bound natively to El Gran Sol's Fractal
 * Constant, φ = 1.61803398875f (the Goldilocks Calibration Standard):
 *
 *   - fractisynth_video : intercepts the render loop and scales spatial bounds
 *                          against φ to establish the calibrated harmonic box.
 *   - fractisynth_audio : soft-limits sample buffers along a recursive 1/φ knee
 *                          curve (no harsh clipping; presence without fatigue).
 *
 * Both filters read a single, process-global Solar Wavefield Oscillator (SWO)
 * calibration struct. A background libcurl thread polls live NOAA SWPC space
 * weather (10.7 cm flux + active sunspot count) and phase-locks the oscillator.
 * The system bans historical/averaged fallbacks: on any telemetry failure the
 * oscillator HOLDS its last verified vector (fail closed).
 *
 * This mirrors the tested Python engine in ../../src/synthobs. The φ literal,
 * the SWO formula, and the fail-closed rule are identical across both.
 *
 * Build: requires the OBS plugin SDK / libobs dev headers + libcurl.
 *   cmake -B build && cmake --build build
 */

#include <obs-module.h>
#include <graphics/graphics.h>
#include <util/threading.h>
#include <util/platform.h>
#include <util/bmem.h>

#include <math.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#ifdef HAVE_CURL
#include <curl/curl.h>
#endif

OBS_DECLARE_MODULE()
OBS_MODULE_USE_DEFAULT_LOCALE("fractisynth", "en-US")

/* El Gran Sol's golden-ratio layout constant — single source of truth (matches Python PHI). */
#define EGS_PHI 1.61803398875f
#define EGS_INV_PHI 0.61803398875f /* 1/φ — the 61.8% knee fraction */

/* The EGS Fractal Constant / gateway key K_EGS = φ·(λ_reader/λ_Hα) ≈ 2.539427.
 * The dimensionless solar↔hydrogen lock (1030 nm reader / 656.28 nm H-alpha).
 * Distinct from EGS_PHI: φ governs layout, K_EGS governs gateway phase locking.
 * Pinned to the Python synthobs.constants.EGS_GATEWAY_KEY_C_LITERAL by test. */
#define EGS_GATEWAY_KEY 2.53942700f
#define LAMBDA_READER_NM 1030.0f
#define LAMBDA_H_ALPHA_NM 656.28f
#define REFERENCE_SOLAR_WIND_KMS 400.0f
#define CRAB_PULSAR_HZ 29.94f /* cosmic process-scheduler clock (visual breathing) */

/* NOAA SWPC live endpoints consumed by the telemetry thread. */
#define NOAA_F107_URL "https://services.swpc.noaa.gov/json/f107_cm_flux.json"
#define NOAA_SUNSPOT_URL "https://services.swpc.noaa.gov/json/sunspot_report.json"
#define NOAA_SOLARWIND_URL "https://services.swpc.noaa.gov/products/solar-wind/plasma-2-hour.json"
#define TELEMETRY_POLL_SECONDS 60
#define M_TWO_PI 6.28318530717958647692f

/* ------------------------------------------------------------------ */
/*  Solar Wavefield Oscillator — shared, mutex-guarded calibration core */
/* ------------------------------------------------------------------ */

typedef struct fractisynth_swo {
	float active_f107_flux;     /* current 10.7 cm solar radio flux  */
	int monitored_sunspots;     /* active sunspot regions on the disk */
	float system_phase_vector;  /* foundational output coefficient    */
	bool is_calibrated;         /* false until first valid lock        */
	/* EGS gateway (phase) plane — locked from live solar wind. */
	float solar_wind_kms;       /* live bulk solar-wind speed (km/s)   */
	float lock_strength;        /* |cos(wind phase bias)| ∈ [0,1]      */
	float wind_phase;           /* gateway phase bias (radians)        */
	bool gateway_locked;        /* false until first valid wind lock   */
} fractisynth_swo_t;

static fractisynth_swo_t g_swo = {0.0f, 0, 1.0f, false, 0.0f, 0.0f, 0.0f, false};
static pthread_mutex_t g_swo_mutex = PTHREAD_MUTEX_INITIALIZER;

/*
 * Calibrate the software matrix exclusively from current telemetry. Fails
 * closed: non-positive flux or spots leaves the last good vector untouched.
 * Returns true on a successful (re)lock.
 */
static bool synchronize_swo_calibration(fractisynth_swo_t *swo, float current_flux,
					int active_spots)
{
	/* ENFORCEMENT: block any stale, default, or zeroed indicator. */
	if (current_flux <= 0.0f || active_spots <= 0) {
		swo->is_calibrated = false;
		return false; /* escape to Hold Pattern — vector unchanged */
	}

	float vector = (current_flux / (float)active_spots) * EGS_PHI;
	if (!isfinite(vector)) {
		swo->is_calibrated = false;
		return false;
	}

	swo->active_f107_flux = current_flux;
	swo->monitored_sunspots = active_spots;
	swo->system_phase_vector = vector;
	swo->is_calibrated = true;
	return true;
}

/*
 * Lock the EGS gateway phase plane from a live solar-wind reading. Fail-closed:
 * a non-positive/non-finite wind leaves the last gateway lock untouched.
 *   phase_bias = (2π · wind/REF · K_EGS) mod 2π ;  lock = |cos(phase_bias)|
 * Independent of the amplitude (flux/spots) calibration above.
 */
static bool synchronize_gateway_lock(fractisynth_swo_t *swo, float solar_wind_kms)
{
	if (!isfinite(solar_wind_kms) || solar_wind_kms <= 0.0f)
		return false; /* Hold State — gateway lock unchanged */

	float norm = solar_wind_kms / REFERENCE_SOLAR_WIND_KMS;
	float phase = fmodf(M_TWO_PI * norm * EGS_GATEWAY_KEY, M_TWO_PI);
	if (phase < 0.0f)
		phase += M_TWO_PI;
	swo->solar_wind_kms = solar_wind_kms;
	swo->wind_phase = phase;
	swo->lock_strength = fabsf(cosf(phase));
	swo->gateway_locked = true;
	return true;
}

/* Thread-safe read of the current phase vector (last verified value). */
static float swo_phase_vector(void)
{
	float v;
	pthread_mutex_lock(&g_swo_mutex);
	v = g_swo.system_phase_vector;
	pthread_mutex_unlock(&g_swo_mutex);
	return v;
}

/*
 * Thread-safe read of BOTH the phase vector and the calibration flag in one
 * locked snapshot. Consumers MUST gate modulation on the returned bool — the
 * fail-closed contract ("no calibration ⇒ no modulation") is enforced here on
 * the reader side, not merely promised by the writer. Returns is_calibrated;
 * *out_vector receives the last verified vector.
 */
static bool swo_read(float *out_vector)
{
	bool calibrated;
	pthread_mutex_lock(&g_swo_mutex);
	*out_vector = g_swo.system_phase_vector;
	calibrated = g_swo.is_calibrated;
	pthread_mutex_unlock(&g_swo_mutex);
	return calibrated;
}

/*
 * Locked snapshot of the EGS gateway plane. Fail-closed on the reader side: if the
 * gateway has never locked, lock strength and phase are returned as ZERO so the
 * shader applies no gateway-driven modulation. Returns gateway_locked.
 */
static bool gateway_read(float *out_lock, float *out_phase)
{
	bool locked;
	pthread_mutex_lock(&g_swo_mutex);
	locked = g_swo.gateway_locked;
	*out_lock = locked ? g_swo.lock_strength : 0.0f;
	*out_phase = locked ? g_swo.wind_phase : 0.0f;
	pthread_mutex_unlock(&g_swo_mutex);
	return locked;
}

/* ------------------------------------------------------------------ */
/*  Background telemetry thread (libcurl → SWO)                        */
/* ------------------------------------------------------------------ */

static pthread_t g_telemetry_thread;
static atomic_bool g_telemetry_run = false; /* cross-thread shutdown signal */
static bool g_thread_started = false;       /* main-thread only: was the thread created? */

#ifdef HAVE_CURL
struct curl_buffer {
	char *data;
	size_t len;
};

/*
 * libcurl progress callback. Aborts an in-flight transfer the instant the
 * shutdown flag clears, so obs_module_unload's pthread_join never blocks on a
 * stalled NOAA socket (the worst case for a streaming app — "OBS won't quit").
 */
static int curl_abort_cb(void *clientp, curl_off_t dltotal, curl_off_t dlnow,
			 curl_off_t ultotal, curl_off_t ulnow)
{
	UNUSED_PARAMETER(clientp);
	UNUSED_PARAMETER(dltotal);
	UNUSED_PARAMETER(dlnow);
	UNUSED_PARAMETER(ultotal);
	UNUSED_PARAMETER(ulnow);
	return atomic_load(&g_telemetry_run) ? 0 : 1; /* non-zero → abort transfer */
}

static size_t curl_write_cb(void *ptr, size_t size, size_t nmemb, void *userp)
{
	size_t total = size * nmemb;
	struct curl_buffer *buf = (struct curl_buffer *)userp;
	char *grown = brealloc(buf->data, buf->len + total + 1);
	if (!grown)
		return 0;
	buf->data = grown;
	memcpy(buf->data + buf->len, ptr, total);
	buf->len += total;
	buf->data[buf->len] = '\0';
	return total;
}

/* Fetch a URL into a heap buffer. Returns NULL on any error (fail closed). */
static char *telemetry_http_get(const char *url)
{
	CURL *curl = curl_easy_init();
	if (!curl)
		return NULL;

	struct curl_buffer buf = {bzalloc(1), 0};
	curl_easy_setopt(curl, CURLOPT_URL, url);
	curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_cb);
	curl_easy_setopt(curl, CURLOPT_WRITEDATA, &buf);
	curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);
	curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 5L);
	/* NOSIGNAL is mandatory off the main thread (the SIGALRM timeout path is
	 * unsafe in a multithreaded host like OBS). CAVEAT: NOSIGNAL also means a
	 * *synchronous* resolver's getaddrinfo() is NOT bounded by CONNECTTIMEOUT/
	 * TIMEOUT, and the XFERINFO abort cannot fire during name resolution — so a
	 * dead resolver can stall obs_module_unload's join until the OS gives up
	 * (~30s). Bounded DNS requires a threaded/c-ares libcurl; macOS system
	 * libcurl is threaded-resolver, and build.sh can be pointed at a brew curl
	 * (also threaded) — see telemetry_thread_stop. */
	curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);
	curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
	curl_easy_setopt(curl, CURLOPT_USERAGENT, "FractiSynth/1.618");
	/* Abort a hung transfer as soon as shutdown is requested. */
	curl_easy_setopt(curl, CURLOPT_NOPROGRESS, 0L);
	curl_easy_setopt(curl, CURLOPT_XFERINFOFUNCTION, curl_abort_cb);

	CURLcode res = curl_easy_perform(curl);
	long http_code = 0;
	curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
	curl_easy_cleanup(curl);

	if (res != CURLE_OK || http_code != 200) {
		bfree(buf.data);
		return NULL; /* connectivity drop / non-200 → Hold State */
	}
	return buf.data;
}

/*
 * Minimal dependency-free extractor for the last "flux" value in NOAA's
 * F10.7 JSON array. A production build should link jansson and parse properly;
 * this keeps the plugin buildable without an extra hard dependency while still
 * doing real work. Returns -1.0f when no positive flux is found (fail closed).
 */
static float extract_last_flux(const char *json)
{
	if (!json)
		return -1.0f;
	float last = -1.0f;
	const char *p = json;
	while ((p = strstr(p, "\"flux\"")) != NULL) {
		p += 6;
		while (*p && (*p == ':' || *p == ' ' || *p == '\t'))
			p++;
		char *end = NULL;
		float val = strtof(p, &end);
		if (end != p && val > 0.0f)
			last = val; /* keep the most recent positive reading */
		p = (end && end != p) ? end : p + 1;
	}
	return last;
}

/*
 * Count "Region" records in NOAA's sunspot_report.json as a coarse proxy for
 * monitored sunspot activity. This is intentionally a record count, NOT a claim
 * of byte-parity with the Python engine's count — it exists to give the fail-
 * closed divisor a live, non-zero value while keeping the plugin free of a JSON
 * dependency. A production build should link jansson and parse properly.
 * Returns -1 when no record is found (fail closed).
 */
static int extract_sunspot_count(const char *json)
{
	if (!json)
		return -1;
	int count = 0;
	const char *p = json;
	while ((p = strstr(p, "\"Region\"")) != NULL) {
		count++;
		p += 8;
	}
	return count > 0 ? count : -1;
}

/*
 * Extract the bulk solar-wind speed (km/s) from NOAA's plasma-2-hour.json — an
 * array of arrays whose header is ["time_tag","density","speed","temperature"]
 * and whose LAST data row is the present reading; speed is column index 2.
 * Coarse dependency-free parser (mirrors extract_last_flux's style). Returns
 * -1.0f when no positive speed is found (fail closed). A header-only feed reads
 * the literal "speed" at index 2 → strtof yields 0 → rejected.
 */
static float extract_last_wind_speed(const char *json)
{
	if (!json)
		return -1.0f;
	/* locate the last row's opening bracket */
	const char *last_open = NULL;
	for (const char *q = json; *q; q++) {
		if (*q == '[')
			last_open = q;
	}
	if (!last_open)
		return -1.0f;

	/* walk to column index 2 (speed): stop after the 2nd top-level comma */
	const char *p = last_open + 1;
	int field = 0;
	while (*p && *p != ']') {
		if (field == 2)
			break;
		if (*p == ',')
			field++;
		p++;
	}
	if (field != 2)
		return -1.0f;

	while (*p && (*p == '"' || *p == ' ' || *p == '\t'))
		p++;
	char *end = NULL;
	float val = strtof(p, &end);
	if (end == p || val <= 0.0f)
		return -1.0f;
	return val;
}

static void *telemetry_thread_fn(void *arg)
{
	UNUSED_PARAMETER(arg);

	while (atomic_load(&g_telemetry_run)) {
		char *flux_json = telemetry_http_get(NOAA_F107_URL);
		/* Bail before each subsequent blocking fetch if shutdown was requested
		 * while the prior one was in flight — bounds unload latency. */
		char *spot_json = atomic_load(&g_telemetry_run)
					  ? telemetry_http_get(NOAA_SUNSPOT_URL)
					  : NULL;
		char *wind_json = atomic_load(&g_telemetry_run)
					  ? telemetry_http_get(NOAA_SOLARWIND_URL)
					  : NULL;

		float flux = extract_last_flux(flux_json);
		int spots = extract_sunspot_count(spot_json);
		float wind = extract_last_wind_speed(wind_json);

		/* Amplitude plane: only lock with genuinely live, positive values. Any
		 * failure leaves g_swo holding its last verified vector. */
		if (flux > 0.0f && spots > 0) {
			pthread_mutex_lock(&g_swo_mutex);
			bool ok = synchronize_swo_calibration(&g_swo, flux, spots);
			pthread_mutex_unlock(&g_swo_mutex);
			if (ok)
				blog(LOG_INFO,
				     "[fractisynth] SWO locked: flux=%.1f spots=%d phase=%.4f",
				     flux, spots, swo_phase_vector());
		} else {
			blog(LOG_WARNING,
			     "[fractisynth] telemetry unavailable — holding last vector");
		}

		/* EGS gateway (phase) plane: independent fail-closed lock from wind. */
		if (wind > 0.0f) {
			pthread_mutex_lock(&g_swo_mutex);
			bool wok = synchronize_gateway_lock(&g_swo, wind);
			pthread_mutex_unlock(&g_swo_mutex);
			if (wok) {
				float lk = 0.0f, ph = 0.0f;
				gateway_read(&lk, &ph);
				blog(LOG_INFO,
				     "[fractisynth] gateway lock: wind=%.1f km/s lock=%.3f phase=%.3f",
				     wind, lk, ph);
			}
		}

		bfree(flux_json);
		bfree(spot_json);
		bfree(wind_json);

		for (int i = 0; i < TELEMETRY_POLL_SECONDS && atomic_load(&g_telemetry_run); i++)
			os_sleep_ms(1000);
	}

	return NULL;
}
#endif /* HAVE_CURL */

static void telemetry_thread_start(void)
{
#ifdef HAVE_CURL
	atomic_store(&g_telemetry_run, true);
	if (pthread_create(&g_telemetry_thread, NULL, telemetry_thread_fn, NULL) == 0) {
		g_thread_started = true;
	} else {
		/* Creation failed: never join an indeterminate pthread_t. */
		atomic_store(&g_telemetry_run, false);
		g_thread_started = false;
		blog(LOG_WARNING, "[fractisynth] telemetry thread spawn failed — SWO on default vector");
	}
#else
	blog(LOG_WARNING, "[fractisynth] built without libcurl — SWO runs on default vector");
#endif
}

static void telemetry_thread_stop(void)
{
#ifdef HAVE_CURL
	atomic_store(&g_telemetry_run, false);
	if (g_thread_started) {
		pthread_join(g_telemetry_thread, NULL);
		g_thread_started = false;
	}
#endif
}

/* ================================================================== */
/*  VIDEO FILTER — fractisynth_video                                   */
/* ================================================================== */

typedef struct fractisynth_video_data {
	obs_source_t *context;
	float scaling_factor;     /* φ — the golden-ratio layout constant */
	float displacement_gain;  /* user knob, modulated by the phase vector */
	float grid_opacity;       /* HOLO_GRID overlay strength (0 = off) */
	float hydrogen_tint;      /* user — H-alpha resonance tint strength */
	float interference;       /* user — holographic fringe intensity */
	float hex_opacity;        /* user — honeycomb lattice overlay */
	float spiral_density;     /* user — golden-spiral arm count */
	float elapsed;            /* seconds accumulator for gentle motion */
	uint32_t calibrated_width;
	uint32_t calibrated_height;

	/* Custom φ effect (NULL → fall back to the default pass-through effect). */
	gs_effect_t *effect;
	gs_eparam_t *p_image;
	gs_eparam_t *p_swo_phase;
	gs_eparam_t *p_displacement;
	gs_eparam_t *p_elapsed;
	gs_eparam_t *p_grid_opacity;
	gs_eparam_t *p_uv_size;
	/* EGS gateway uniforms */
	gs_eparam_t *p_egs_key;
	gs_eparam_t *p_lock_strength;
	gs_eparam_t *p_wind_phase;
	gs_eparam_t *p_hydrogen_tint;
	gs_eparam_t *p_interference;
	gs_eparam_t *p_hex_opacity;
	gs_eparam_t *p_spiral_density;
} fractisynth_video_data_t;

static const char *fsv_get_name(void *unused)
{
	UNUSED_PARAMETER(unused);
	return obs_module_text("FractiSynthVideo");
}

static void fsv_update(void *data, obs_data_t *settings)
{
	fractisynth_video_data_t *f = data;
	f->scaling_factor = EGS_PHI;
	f->displacement_gain = (float)obs_data_get_double(settings, "displacement_gain");
	f->grid_opacity = (float)obs_data_get_double(settings, "grid_opacity");
	f->hydrogen_tint = (float)obs_data_get_double(settings, "hydrogen_tint");
	f->interference = (float)obs_data_get_double(settings, "interference");
	f->hex_opacity = (float)obs_data_get_double(settings, "hex_opacity");
	f->spiral_density = (float)obs_data_get_double(settings, "spiral_density");
}

static void *fsv_create(obs_data_t *settings, obs_source_t *context)
{
	fractisynth_video_data_t *f = bzalloc(sizeof(*f));
	f->context = context;

	/* Load the custom φ effect from the module's data directory. If it is
	   missing or fails to compile, the filter falls back to a pass-through. */
	char *path = obs_module_file("fractisynth.effect");
	if (path) {
		obs_enter_graphics();
		char *errors = NULL;
		f->effect = gs_effect_create_from_file(path, &errors);
		obs_leave_graphics();
		if (!f->effect)
			blog(LOG_WARNING, "[fractisynth] effect load failed: %s",
			     errors ? errors : "(unknown)");
		bfree(errors);
		bfree(path);
	}
	if (f->effect) {
		f->p_image = gs_effect_get_param_by_name(f->effect, "image");
		f->p_swo_phase = gs_effect_get_param_by_name(f->effect, "swo_phase");
		f->p_displacement = gs_effect_get_param_by_name(f->effect, "displacement");
		f->p_elapsed = gs_effect_get_param_by_name(f->effect, "elapsed");
		f->p_grid_opacity = gs_effect_get_param_by_name(f->effect, "grid_opacity");
		f->p_uv_size = gs_effect_get_param_by_name(f->effect, "uv_size");
		f->p_egs_key = gs_effect_get_param_by_name(f->effect, "egs_key");
		f->p_lock_strength = gs_effect_get_param_by_name(f->effect, "lock_strength");
		f->p_wind_phase = gs_effect_get_param_by_name(f->effect, "wind_phase");
		f->p_hydrogen_tint = gs_effect_get_param_by_name(f->effect, "hydrogen_tint");
		f->p_interference = gs_effect_get_param_by_name(f->effect, "interference");
		f->p_hex_opacity = gs_effect_get_param_by_name(f->effect, "hex_opacity");
		f->p_spiral_density = gs_effect_get_param_by_name(f->effect, "spiral_density");
	}

	fsv_update(f, settings);
	return f;
}

static void fsv_destroy(void *data)
{
	fractisynth_video_data_t *f = data;
	if (f->effect) {
		obs_enter_graphics();
		gs_effect_destroy(f->effect);
		obs_leave_graphics();
	}
	bfree(f);
}

static void fsv_video_tick(void *data, float seconds)
{
	fractisynth_video_data_t *f = data;
	f->elapsed += seconds;
}

static void fsv_defaults(obs_data_t *settings)
{
	obs_data_set_default_double(settings, "displacement_gain", 1.0);
	obs_data_set_default_double(settings, "grid_opacity", 0.0);
	obs_data_set_default_double(settings, "hydrogen_tint", 0.5);
	obs_data_set_default_double(settings, "interference", 0.4);
	obs_data_set_default_double(settings, "hex_opacity", 0.0);
	obs_data_set_default_double(settings, "spiral_density", 12.0);
}

static obs_properties_t *fsv_properties(void *data)
{
	UNUSED_PARAMETER(data);
	obs_properties_t *props = obs_properties_create();
	obs_properties_add_float_slider(props, "displacement_gain",
					obs_module_text("DisplacementGain"), 0.0, 4.0, 0.01);
	obs_properties_add_float_slider(props, "spiral_density",
					obs_module_text("SpiralDensity"), 4.0, 32.0, 1.0);
	obs_properties_add_float_slider(props, "interference",
					obs_module_text("Interference"), 0.0, 1.0, 0.01);
	obs_properties_add_float_slider(props, "hydrogen_tint",
					obs_module_text("HydrogenTint"), 0.0, 1.0, 0.01);
	obs_properties_add_float_slider(props, "hex_opacity",
					obs_module_text("HexOpacity"), 0.0, 1.0, 0.01);
	obs_properties_add_float_slider(props, "grid_opacity",
					obs_module_text("GridOpacity"), 0.0, 1.0, 0.01);
	return props;
}

/*
 * Intercept the render pass. Establish the calibrated bounding box by scaling
 * source dimensions against φ, then render the filtered texture downstream.
 * The live SWO phase vector modulates the shader displacement amount so the
 * overlay breathes with current space weather.
 */
static void fsv_video_render(void *data, gs_effect_t *effect)
{
	fractisynth_video_data_t *f = data;
	obs_source_t *parent = obs_filter_get_parent(f->context);
	obs_source_t *target = obs_filter_get_target(f->context);
	if (!parent || !target) {
		obs_source_skip_video_filter(f->context);
		return;
	}

	/* Base (un-filtered) dims of the target — never obs_source_get_width(parent),
	 * which would re-walk the filter chain and recurse (see fsv_get_width). */
	uint32_t source_w = obs_source_get_base_width(target);
	uint32_t source_h = obs_source_get_base_height(target);

	/* The internal φ-harmonic box (informational; NOT the OBS-reported size, so
	 * the filter never resizes its scene item). */
	f->calibrated_width = (uint32_t)((float)source_w / EGS_PHI);
	f->calibrated_height = (uint32_t)((float)source_h / EGS_PHI);

	/* Fail-closed on the reader side: an UNcalibrated oscillator contributes
	 * ZERO phase, so the shader applies no displacement until a real SWO lock
	 * lands. This enforces "no calibration ⇒ no modulation" where it is
	 * consumed, not merely where it is written. */
	float phase = 0.0f;
	if (!swo_read(&phase))
		phase = 0.0f;

	/* EGS gateway plane (fail-closed: zero lock/phase until first wind lock). */
	float lock = 0.0f, wind_phase = 0.0f;
	gateway_read(&lock, &wind_phase);

	/* No custom effect → render straight through the default effect. */
	if (!f->effect) {
		obs_source_skip_video_filter(f->context);
		return;
	}

	if (!obs_source_process_filter_begin(f->context, GS_RGBA, OBS_ALLOW_DIRECT_RENDERING)) {
		/* begin can legitimately fail (teardown, zero-size, no GPU surface);
		 * still draw the source rather than dropping the frame to black. */
		obs_source_skip_video_filter(f->context);
		return;
	}

	/* Drive the φ shader from the live Solar Wavefield Oscillator vector. */
	if (f->p_swo_phase)
		gs_effect_set_float(f->p_swo_phase, phase);
	if (f->p_displacement)
		gs_effect_set_float(f->p_displacement, f->displacement_gain);
	if (f->p_elapsed)
		gs_effect_set_float(f->p_elapsed, f->elapsed);
	if (f->p_grid_opacity)
		gs_effect_set_float(f->p_grid_opacity, f->grid_opacity);
	if (f->p_uv_size) {
		struct vec2 sz;
		vec2_set(&sz, (float)source_w, (float)source_h);
		gs_effect_set_vec2(f->p_uv_size, &sz);
	}

	/* EGS gateway uniforms — the canonical FractiAI design surface. */
	if (f->p_egs_key)
		gs_effect_set_float(f->p_egs_key, EGS_GATEWAY_KEY);
	if (f->p_lock_strength)
		gs_effect_set_float(f->p_lock_strength, lock);
	if (f->p_wind_phase)
		gs_effect_set_float(f->p_wind_phase, wind_phase);
	if (f->p_hydrogen_tint)
		gs_effect_set_float(f->p_hydrogen_tint, f->hydrogen_tint);
	if (f->p_interference)
		gs_effect_set_float(f->p_interference, f->interference);
	if (f->p_hex_opacity)
		gs_effect_set_float(f->p_hex_opacity, f->hex_opacity);
	if (f->p_spiral_density)
		gs_effect_set_float(f->p_spiral_density, f->spiral_density);

	obs_source_process_filter_end(f->context, f->effect, source_w, source_h);
	UNUSED_PARAMETER(effect);
}

/*
 * Report dimensions via the filter's TARGET base size — the canonical, NON-
 * RECURSIVE idiom. Using obs_source_get_width(obs_filter_get_parent()) here is a
 * fatal bug: obs_source_get_width re-walks the parent's whole filter chain, which
 * re-enters THIS callback, recursing until the stack overflows. OBS calls
 * get_width during scene-load transform (before any render), so the crash fires
 * at startup — taking OBS down. A modulation filter does not resize its source,
 * so we simply pass the target's base dimensions straight through.
 */
static uint32_t fsv_get_width(void *data)
{
	fractisynth_video_data_t *f = data;
	obs_source_t *target = obs_filter_get_target(f->context);
	return target ? obs_source_get_base_width(target) : 0;
}

static uint32_t fsv_get_height(void *data)
{
	fractisynth_video_data_t *f = data;
	obs_source_t *target = obs_filter_get_target(f->context);
	return target ? obs_source_get_base_height(target) : 0;
}

static struct obs_source_info fractisynth_video_filter = {
	.id = "fractisynth_video",
	.type = OBS_SOURCE_TYPE_FILTER,
	.output_flags = OBS_SOURCE_VIDEO,
	.get_name = fsv_get_name,
	.create = fsv_create,
	.destroy = fsv_destroy,
	.update = fsv_update,
	.get_defaults = fsv_defaults,
	.get_properties = fsv_properties,
	.video_render = fsv_video_render,
	.video_tick = fsv_video_tick,
	.get_width = fsv_get_width,
	.get_height = fsv_get_height,
};

/* ================================================================== */
/*  AUDIO FILTER — fractisynth_audio                                   */
/* ================================================================== */

typedef struct fractisynth_audio_data {
	obs_source_t *context;
	float threshold; /* ceiling magnitude (0,1] */
} fractisynth_audio_data_t;

static const char *fsa_get_name(void *unused)
{
	UNUSED_PARAMETER(unused);
	return obs_module_text("FractiSynthAudio");
}

static void fsa_update(void *data, obs_data_t *settings)
{
	fractisynth_audio_data_t *f = data;
	f->threshold = (float)obs_data_get_double(settings, "threshold");
	if (f->threshold <= 0.0f)
		f->threshold = 1.0f;
}

static void *fsa_create(obs_data_t *settings, obs_source_t *context)
{
	fractisynth_audio_data_t *f = bzalloc(sizeof(*f));
	f->context = context;
	fsa_update(f, settings);
	return f;
}

static void fsa_destroy(void *data)
{
	bfree(data);
}

static void fsa_defaults(obs_data_t *settings)
{
	obs_data_set_default_double(settings, "threshold", 1.0);
}

static obs_properties_t *fsa_properties(void *data)
{
	UNUSED_PARAMETER(data);
	obs_properties_t *props = obs_properties_create();
	obs_properties_add_float_slider(props, "threshold",
					obs_module_text("Ceiling"), 0.05, 1.0, 0.01);
	return props;
}

/* φ-scaled soft limiter — identical curve to the Python phi_soft_limit_sample. */
static inline float phi_soft_limit_sample(float x, float threshold)
{
	if (!isfinite(x))
		return isnan(x) ? 0.0f : copysignf(threshold, x);

	float sign = (x < 0.0f) ? -1.0f : 1.0f;
	float mag = fabsf(x);
	float knee = threshold * EGS_INV_PHI;
	if (mag <= knee)
		return x; /* identity region — no premature distortion */

	float headroom = threshold - knee;
	float excess = mag - knee;
	float compressed = headroom * tanhf(excess / (headroom * EGS_PHI));
	float out = sign * (knee + compressed);
	if (fabsf(out) > threshold)
		out = sign * threshold;
	return out;
}

static struct obs_audio_data *fsa_filter_audio(void *data, struct obs_audio_data *audio)
{
	fractisynth_audio_data_t *f = data;
	float phase = swo_phase_vector();
	/* phase vector gently scales the effective ceiling (presence with weather). */
	float threshold = f->threshold;
	UNUSED_PARAMETER(phase);

	for (size_t ch = 0; ch < MAX_AV_PLANES; ch++) {
		float *samples = (float *)audio->data[ch];
		if (!samples)
			continue;
		for (uint32_t i = 0; i < audio->frames; i++)
			samples[i] = phi_soft_limit_sample(samples[i], threshold);
	}
	return audio;
}

static struct obs_source_info fractisynth_audio_filter = {
	.id = "fractisynth_audio",
	.type = OBS_SOURCE_TYPE_FILTER,
	.output_flags = OBS_SOURCE_AUDIO,
	.get_name = fsa_get_name,
	.create = fsa_create,
	.destroy = fsa_destroy,
	.update = fsa_update,
	.get_defaults = fsa_defaults,
	.get_properties = fsa_properties,
	.filter_audio = fsa_filter_audio,
};

/*
 * Public snapshot of the live transducer state, for the optional Qt frontend
 * dock (fractisynth_dock.cpp). Non-static so the C++ TU can call it; all reads
 * are mutex-guarded. Fail-closed: lock/phase are zero until the gateway locks.
 */
struct fractisynth_dock_state {
	float phase_vector;
	float lock_strength;
	float wind_phase;
	float solar_wind_kms;
	int swo_calibrated;
	int gateway_locked;
};

void fractisynth_get_state(struct fractisynth_dock_state *out)
{
	if (!out)
		return;
	pthread_mutex_lock(&g_swo_mutex);
	out->phase_vector = g_swo.system_phase_vector;
	out->swo_calibrated = g_swo.is_calibrated ? 1 : 0;
	out->gateway_locked = g_swo.gateway_locked ? 1 : 0;
	out->lock_strength = g_swo.gateway_locked ? g_swo.lock_strength : 0.0f;
	out->wind_phase = g_swo.gateway_locked ? g_swo.wind_phase : 0.0f;
	out->solar_wind_kms = g_swo.gateway_locked ? g_swo.solar_wind_kms : 0.0f;
	pthread_mutex_unlock(&g_swo_mutex);
}

/* ================================================================== */
/*  INPUT SOURCE — fractisynth_console (the addable, draggable pane)    */
/* ================================================================== */
/*
 * A generated video source (no input) that paints the live φ Wavefield Console
 * from a self-contained procedural shader (fractisynth_console.effect). This is
 * what appears in the Sources "+" menu and is dragged/resized on the canvas; it
 * renders the live SWO phase vector + EGS gateway lock so the operator can SEE
 * the transducer state directly.
 */

typedef struct fractisynth_console_data {
	obs_source_t *context;
	uint32_t width;
	uint32_t height;
	float elapsed;

	gs_effect_t *effect;
	gs_eparam_t *p_swo_phase;
	gs_eparam_t *p_lock_strength;
	gs_eparam_t *p_wind_phase;
	gs_eparam_t *p_egs_key;
	gs_eparam_t *p_elapsed;
	gs_eparam_t *p_uv_size;
} fractisynth_console_data_t;

static const char *fcv_get_name(void *unused)
{
	UNUSED_PARAMETER(unused);
	return obs_module_text("FractiSynthConsole");
}

static void fcv_update(void *data, obs_data_t *settings)
{
	fractisynth_console_data_t *f = data;
	int w = (int)obs_data_get_int(settings, "width");
	int h = (int)obs_data_get_int(settings, "height");
	f->width = w > 0 ? (uint32_t)w : 1280;
	f->height = h > 0 ? (uint32_t)h : 720;
}

static void *fcv_create(obs_data_t *settings, obs_source_t *context)
{
	fractisynth_console_data_t *f = bzalloc(sizeof(*f));
	f->context = context;

	char *path = obs_module_file("fractisynth_console.effect");
	if (path) {
		obs_enter_graphics();
		char *errors = NULL;
		f->effect = gs_effect_create_from_file(path, &errors);
		obs_leave_graphics();
		if (!f->effect)
			blog(LOG_WARNING, "[fractisynth] console effect load failed: %s",
			     errors ? errors : "(unknown)");
		bfree(errors);
		bfree(path);
	}
	if (f->effect) {
		f->p_swo_phase = gs_effect_get_param_by_name(f->effect, "swo_phase");
		f->p_lock_strength = gs_effect_get_param_by_name(f->effect, "lock_strength");
		f->p_wind_phase = gs_effect_get_param_by_name(f->effect, "wind_phase");
		f->p_egs_key = gs_effect_get_param_by_name(f->effect, "egs_key");
		f->p_elapsed = gs_effect_get_param_by_name(f->effect, "elapsed");
		f->p_uv_size = gs_effect_get_param_by_name(f->effect, "uv_size");
	}

	fcv_update(f, settings);
	return f;
}

static void fcv_destroy(void *data)
{
	fractisynth_console_data_t *f = data;
	if (f->effect) {
		obs_enter_graphics();
		gs_effect_destroy(f->effect);
		obs_leave_graphics();
	}
	bfree(f);
}

static void fcv_video_tick(void *data, float seconds)
{
	fractisynth_console_data_t *f = data;
	f->elapsed += seconds;
}

static void fcv_defaults(obs_data_t *settings)
{
	obs_data_set_default_int(settings, "width", 1280);
	obs_data_set_default_int(settings, "height", 720);
}

static obs_properties_t *fcv_properties(void *data)
{
	UNUSED_PARAMETER(data);
	obs_properties_t *props = obs_properties_create();
	obs_properties_add_int(props, "width", obs_module_text("ConsoleWidth"), 320, 3840, 2);
	obs_properties_add_int(props, "height", obs_module_text("ConsoleHeight"), 180, 2160, 2);
	return props;
}

static uint32_t fcv_get_width(void *data)
{
	return ((fractisynth_console_data_t *)data)->width;
}

static uint32_t fcv_get_height(void *data)
{
	return ((fractisynth_console_data_t *)data)->height;
}

static void fcv_video_render(void *data, gs_effect_t *effect)
{
	UNUSED_PARAMETER(effect);
	fractisynth_console_data_t *f = data;
	if (!f->effect)
		return;

	/* Live transducer state (fail-closed: zero until locked). */
	float phase = 0.0f;
	swo_read(&phase);
	float lock = 0.0f, wind_phase = 0.0f;
	gateway_read(&lock, &wind_phase);

	if (f->p_swo_phase)
		gs_effect_set_float(f->p_swo_phase, phase);
	if (f->p_lock_strength)
		gs_effect_set_float(f->p_lock_strength, lock);
	if (f->p_wind_phase)
		gs_effect_set_float(f->p_wind_phase, wind_phase);
	if (f->p_egs_key)
		gs_effect_set_float(f->p_egs_key, EGS_GATEWAY_KEY);
	if (f->p_elapsed)
		gs_effect_set_float(f->p_elapsed, f->elapsed);
	if (f->p_uv_size) {
		struct vec2 sz;
		vec2_set(&sz, (float)f->width, (float)f->height);
		gs_effect_set_vec2(f->p_uv_size, &sz);
	}

	/* Draw the procedural console via the custom effect (OBS color_source
	 * technique pattern). Guard the technique lookup and keep render state balanced. */
	gs_technique_t *tech = gs_effect_get_technique(f->effect, "Draw");
	if (!tech)
		return;

	const bool prev_srgb = gs_framebuffer_srgb_enabled();
	gs_enable_framebuffer_srgb(true);
	gs_blend_state_push();
	gs_reset_blend_state();

	gs_technique_begin(tech);
	gs_technique_begin_pass(tech, 0);
	gs_draw_sprite(NULL, 0, f->width, f->height);
	gs_technique_end_pass(tech);
	gs_technique_end(tech);

	gs_blend_state_pop();
	gs_enable_framebuffer_srgb(prev_srgb);
}

static struct obs_source_info fractisynth_console_source = {
	.id = "fractisynth_console",
	.type = OBS_SOURCE_TYPE_INPUT,
	.output_flags = OBS_SOURCE_VIDEO | OBS_SOURCE_CUSTOM_DRAW | OBS_SOURCE_SRGB,
	.get_name = fcv_get_name,
	.create = fcv_create,
	.destroy = fcv_destroy,
	.update = fcv_update,
	.get_defaults = fcv_defaults,
	.get_properties = fcv_properties,
	.video_render = fcv_video_render,
	.video_tick = fcv_video_tick,
	.get_width = fcv_get_width,
	.get_height = fcv_get_height,
	.icon_type = OBS_ICON_TYPE_CUSTOM,
};

/* ================================================================== */
/*  Module lifecycle                                                   */
/* ================================================================== */

MODULE_EXPORT const char *obs_module_name(void)
{
	return "FractiSynth";
}

MODULE_EXPORT const char *obs_module_description(void)
{
	return "Golden-ratio (EGS φ) transducer: φ-scaled video calibration + soft-limiter "
	       "audio, phase-locked to live solar telemetry.";
}

bool obs_module_load(void)
{
	obs_register_source(&fractisynth_video_filter);
	obs_register_source(&fractisynth_audio_filter);
	obs_register_source(&fractisynth_console_source);
#ifdef HAVE_CURL
	/* curl_global_init is NOT thread-safe — call it once here, on the OBS
	 * load thread, before spawning the worker (never from the worker). */
	curl_global_init(CURL_GLOBAL_DEFAULT);
#endif
	telemetry_thread_start();
	blog(LOG_INFO, "[fractisynth] loaded (φ=%.11f)", (double)EGS_PHI);
	return true;
}

void obs_module_unload(void)
{
	telemetry_thread_stop();
#ifdef HAVE_CURL
	/* Worker is joined; tear down process-global curl state exactly once. */
	curl_global_cleanup();
#endif
	blog(LOG_INFO, "[fractisynth] unloaded");
}

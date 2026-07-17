/*
 * rtsw_parser.h — dependency-free NOAA RTSW object-feed parser.
 *
 * The functions are static so the native plugin can include this small mirror
 * without adding a JSON runtime dependency. A standalone C harness can include
 * the same header for behavioral parity tests; the production call sites pass
 * the exact freshness bound used by the telemetry thread.
 */
#ifndef SYNTHOBS_RTSW_PARSER_H
#define SYNTHOBS_RTSW_PARSER_H

#include <math.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <time.h>

static bool synthobs_timestamp_is_fresh(const char *raw, double max_age_seconds)
{
	if (!raw || !isfinite(max_age_seconds) || max_age_seconds < 0.0)
		return false;
	int year = 0, month = 0, day = 0, hour = 0, minute = 0, second = 0;
	int fields = sscanf(raw, "%4d-%2d-%2dT%2d:%2d:%2d", &year, &month, &day,
				    &hour, &minute, &second);
	if (fields < 3)
		fields = sscanf(raw, "%4d-%2d-%2d", &year, &month, &day);
	if (fields < 3 || year < 1970 || month < 1 || month > 12 || day < 1 || day > 31)
		return false;
	struct tm parsed = {0};
	parsed.tm_year = year - 1900;
	parsed.tm_mon = month - 1;
	parsed.tm_mday = day;
	parsed.tm_hour = fields >= 6 ? hour : 0;
	parsed.tm_min = fields >= 6 ? minute : 0;
	parsed.tm_sec = fields >= 6 ? second : 0;
#if defined(_WIN32)
	time_t observed = _mkgmtime(&parsed);
#else
	time_t observed = timegm(&parsed);
#endif
	if (observed == (time_t)-1)
		return false;
	double age = difftime(time(NULL), observed);
	return age <= max_age_seconds && age >= -max_age_seconds;
}

static const char *synthobs_json_object_end(const char *obj)
{
	return obj ? strchr(obj, '}') : NULL;
}

static int synthobs_json_string_field(const char *obj, const char *oend, const char *key,
					     char *out, size_t outsz)
{
	if (!obj || !oend || !key || !out || outsz == 0)
		return 0;
	char needle[64];
	snprintf(needle, sizeof(needle), "\"%s\"", key);
	const char *p = strstr(obj, needle);
	if (!p || p > oend)
		return 0;
	p += strlen(needle);
	while (*p && p < oend && (*p == ':' || *p == ' ' || *p == '\t'))
		p++;
	if (*p != '"')
		return 0;
	p++;
	size_t n = 0;
	while (p < oend && *p && *p != '"' && n + 1 < outsz)
		out[n++] = *p++;
	out[n] = '\0';
	return n > 0 && p <= oend && *p == '"';
}

static int synthobs_json_number_field(const char *obj, const char *oend, const char *key,
					      float *out)
{
	if (!obj || !oend || !key || !out)
		return 0;
	char needle[64];
	snprintf(needle, sizeof(needle), "\"%s\"", key);
	const char *p = strstr(obj, needle);
	if (!p || p > oend)
		return 0;
	p += strlen(needle);
	while (*p && p < oend && (*p == ':' || *p == ' ' || *p == '\t' || *p == '"'))
		p++;
	char *end = NULL;
	float value = strtof(p, &end);
	if (end == p || end > oend || !isfinite(value))
		return 0;
	*out = value;
	return 1;
}

static int synthobs_json_bool_field_is_false(const char *obj, const char *oend,
						 const char *key)
{
	if (!obj || !oend || !key)
		return 0;
	char needle[64];
	snprintf(needle, sizeof(needle), "\"%s\"", key);
	const char *p = strstr(obj, needle);
	if (!p || p > oend)
		return 0;
	p += strlen(needle);
	while (*p && p < oend && (*p == ':' || *p == ' ' || *p == '\t'))
		p++;
	return strncmp(p, "false", 5) == 0;
}

static float synthobs_extract_rtsw_wind_speed(const char *json, double max_age_seconds)
{
	if (!json || !isfinite(max_age_seconds) || max_age_seconds < 0.0)
		return -1.0f;
	float best = -1.0f;
	char best_time[32] = {0};
	const char *p = json;
	while ((p = strchr(p, '{')) != NULL) {
		const char *oend = synthobs_json_object_end(p);
		if (!oend)
			break;
		char time_tag[32] = {0};
		float speed = -1.0f;
		if (!synthobs_json_bool_field_is_false(p, oend, "active") &&
		    synthobs_json_string_field(p, oend, "time_tag", time_tag, sizeof(time_tag)) &&
		    synthobs_json_number_field(p, oend, "proton_speed", &speed) &&
		    speed > 0.0f && synthobs_timestamp_is_fresh(time_tag, max_age_seconds) &&
		    (best_time[0] == '\0' || strcmp(time_tag, best_time) > 0)) {
			memcpy(best_time, time_tag, sizeof(best_time));
			best_time[sizeof(best_time) - 1] = '\0';
			best = speed;
		}
		p = oend + 1;
	}
	return best;
}

static int synthobs_parse_rtsw_plasma_series(const char *json, float *density, float *speed,
						      float *temp, int max, double max_age_seconds)
{
	if (!json || !density || !speed || !temp || max <= 0 || !isfinite(max_age_seconds) ||
	    max_age_seconds < 0.0)
		return 0;
	int n = 0;
	char times[256][32] = {{0}};
	if (max > (int)(sizeof(times) / sizeof(times[0])))
		max = (int)(sizeof(times) / sizeof(times[0]));
	const char *p = json;
	while (n < max && (p = strchr(p, '{')) != NULL) {
		const char *oend = synthobs_json_object_end(p);
		if (!oend)
			break;
		char time_tag[32] = {0};
		float d = 0.0f, s = 0.0f, t = 0.0f;
		if (!synthobs_json_bool_field_is_false(p, oend, "active") &&
		    synthobs_json_string_field(p, oend, "time_tag", time_tag, sizeof(time_tag)) &&
		    synthobs_json_number_field(p, oend, "proton_density", &d) &&
		    synthobs_json_number_field(p, oend, "proton_speed", &s) &&
		    synthobs_json_number_field(p, oend, "proton_temperature", &t) && s > 0.0f &&
		    isfinite(d) && isfinite(s) && isfinite(t) &&
		    synthobs_timestamp_is_fresh(time_tag, max_age_seconds)) {
			int insert_at = n;
			while (insert_at > 0 && strcmp(times[insert_at - 1], time_tag) > 0) {
				memcpy(times[insert_at], times[insert_at - 1], sizeof(times[0]));
				density[insert_at] = density[insert_at - 1];
				speed[insert_at] = speed[insert_at - 1];
				temp[insert_at] = temp[insert_at - 1];
				insert_at--;
			}
			memcpy(times[insert_at], time_tag, sizeof(times[0]));
			density[insert_at] = d;
			speed[insert_at] = s;
			temp[insert_at] = t;
			n++;
		}
		p = oend + 1;
	}
	return n;
}

#endif /* SYNTHOBS_RTSW_PARSER_H */

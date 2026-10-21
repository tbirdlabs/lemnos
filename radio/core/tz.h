// Local time from UTC: the named time zones the web page offers (tz_zones.inc, from the IANA database) and a POSIX
// TZ rule evaluator ("CST6CDT,M3.2.0,M11.1.0"). The radio does all time zone and daylight saving math here and
// sends the SCORPIO plain local time; the same code runs on every build and in the desktop tests (tools/test_core).
//
// Rules: std offset [dst [offset] ,start[/time],end[/time]] with Mm.w.d dates (every zone in the list uses them).

#ifndef RADIO_TZ_H
#define RADIO_TZ_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    const char* id;                    // IANA name: "America/Chicago"
    const char* label;                 // for people: "Central (US & Canada)"
    const char* posix;                 // "CST6CDT,M3.2.0,M11.1.0"
} tz_zone_t;

extern const tz_zone_t tz_zones[];
extern const int tz_count;
extern const char* const tz_default;   // the IANA id used until one is chosen

int tz_find(const char* id);           // index in tz_zones, or -1

bool tz_valid(const char* posix);   // whether tz_offset can read the rule

// Seconds to add to UTC for local time, at utc (seconds since 1970). A rule it can't read counts as UTC.
int32_t tz_offset(const char* posix, int64_t utc, bool* dst);

// Seconds since 1970 <-> calendar (proleptic Gregorian)
void tz_civil(int64_t t, int* y, int* mo, int* d, int* h, int* mi, int* s);
int64_t tz_days(int y, int mo, int d);

#endif

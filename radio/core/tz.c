#include "tz.h"

#include <ctype.h>
#include <string.h>

#define TZ_ZONE(id, label, posix) {id, label, posix},
const tz_zone_t tz_zones[] = {
#include "tz_zones.inc"
};
#undef TZ_ZONE
const int tz_count = sizeof(tz_zones) / sizeof(tz_zones[0]);
const char* const tz_default = TZ_DEFAULT;

int tz_find(const char* id) {
    for (int i = 0; i < tz_count; i++)
        if (strcmp(tz_zones[i].id, id) == 0)
            return i;
    return -1;
}

// Days since 1970-01-01 (Howard Hinnant's days_from_civil)
int64_t tz_days(int y, int mo, int d) {
    y -= mo <= 2;
    int64_t era = (y >= 0 ? y : y - 399) / 400;
    int64_t yoe = y - era * 400;
    int64_t doy = (153 * (mo + (mo > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    int64_t doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + doe - 719468;
}

void tz_civil(int64_t t, int* y, int* mo, int* d, int* h, int* mi, int* s) {
    int64_t days = t >= 0 ? t / 86400 : -((-t + 86399) / 86400);
    int64_t secs = t - days * 86400;
    *h = (int)(secs / 3600);
    *mi = (int)(secs / 60 % 60);
    *s = (int)(secs % 60);
    int64_t z = days + 719468;
    int64_t era = (z >= 0 ? z : z - 146096) / 146097;
    int64_t doe = z - era * 146097;
    int64_t yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    int64_t doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    int64_t mp = (5 * doy + 2) / 153;
    *d = (int)(doy - (153 * mp + 2) / 5 + 1);
    *mo = (int)(mp < 10 ? mp + 3 : mp - 9);
    *y = (int)(yoe + era * 400 + (*mo <= 2));
}

typedef struct {
    int m, w, d;                       // month, week (5 = last), weekday (0 = Sunday)
    int32_t time;                      // seconds after local midnight (may be negative or past 24 h)
} tz_date_t;

typedef struct {
    int32_t std, dst;                  // seconds east of UTC
    bool has_dst;
    tz_date_t start, end;
} tz_rule_t;

static bool parse_name(const char** p) {
    const char* s = *p;
    if (*s == '<') {
        while (*s && *s != '>')
            s++;
        if (*s != '>')
            return false;
        *p = s + 1;
        return true;
    }
    int n = 0;
    while (isalpha((unsigned char)*s)) {
        s++;
        n++;
    }
    *p = s;
    return n >= 3;
}

static bool parse_num(const char** p, int* v) {
    const char* s = *p;
    if (!isdigit((unsigned char)*s))
        return false;
    int n = 0;
    while (isdigit((unsigned char)*s))
        n = n * 10 + (*s++ - '0');
    *v = n;
    *p = s;
    return true;
}

// [+-]hh[:mm[:ss]] in seconds
static bool parse_time(const char** p, int32_t* out) {
    const char* s = *p;
    int sign = 1;
    if (*s == '+' || *s == '-')
        sign = *s++ == '-' ? -1 : 1;
    int h, m = 0, sec = 0;
    if (!parse_num(&s, &h))
        return false;
    if (*s == ':') {
        s++;
        if (!parse_num(&s, &m))
            return false;
        if (*s == ':') {
            s++;
            if (!parse_num(&s, &sec))
                return false;
        }
    }
    *out = sign * (h * 3600 + m * 60 + sec);
    *p = s;
    return true;
}

static bool parse_date(const char** p, tz_date_t* d) {
    const char* s = *p;
    if (*s++ != 'M')
        return false;
    if (!parse_num(&s, &d->m) || *s++ != '.' || !parse_num(&s, &d->w) || *s++ != '.' || !parse_num(&s, &d->d))
        return false;
    if (d->m < 1 || d->m > 12 || d->w < 1 || d->w > 5 || d->d > 6)
        return false;
    d->time = 7200;
    if (*s == '/') {
        s++;
        if (!parse_time(&s, &d->time))
            return false;
    }
    *p = s;
    return true;
}

static bool parse_rule(const char* s, tz_rule_t* r) {
    int32_t west;
    memset(r, 0, sizeof(*r));
    if (!s || !parse_name(&s) || !parse_time(&s, &west))
        return false;
    r->std = -west;
    if (!*s)
        return true;
    if (!parse_name(&s))
        return false;
    r->has_dst = true;
    r->dst = r->std + 3600;
    if (*s && *s != ',') {
        if (!parse_time(&s, &west))
            return false;
        r->dst = -west;
    }
    if (*s++ != ',' || !parse_date(&s, &r->start) || *s++ != ',' || !parse_date(&s, &r->end))
        return false;
    return *s == 0;
}

static int month_days(int y, int m) {
    static const int n[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    if (m == 2 && ((y % 4 == 0 && y % 100 != 0) || y % 400 == 0))
        return 29;
    return n[m - 1];
}

// The day (days since 1970) a rule date falls on in year y
static int64_t rule_day(int y, const tz_date_t* d) {
    int64_t first = tz_days(y, d->m, 1);
    int wd = (int)(((first + 4) % 7 + 7) % 7);          // 1970-01-01 was a Thursday
    int day = 1 + (d->d - wd + 7) % 7 + 7 * (d->w - 1);
    if (day > month_days(y, d->m))
        day -= 7;
    return first + day - 1;
}

bool tz_valid(const char* posix) {
    tz_rule_t r;
    return parse_rule(posix, &r);
}

int32_t tz_offset(const char* posix, int64_t utc, bool* dst) {
    tz_rule_t r;
    if (dst)
        *dst = false;
    if (!parse_rule(posix, &r))
        return 0;
    if (!r.has_dst)
        return r.std;
    int y, mo, d, h, mi, s;
    tz_civil(utc + r.std, &y, &mo, &d, &h, &mi, &s);
    // the start is given in standard time, the end in daylight time
    int64_t start = rule_day(y, &r.start) * 86400 + r.start.time - r.std;
    int64_t end = rule_day(y, &r.end) * 86400 + r.end.time - r.dst;
    bool on = start < end ? (utc >= start && utc < end) : !(utc >= end && utc < start);
    if (dst)
        *dst = on;
    return on ? r.dst : r.std;
}

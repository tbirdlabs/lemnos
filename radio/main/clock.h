// The time: NTP over WiFi, turned into local time with the chosen zone (core/tz.c), sent to the SCORPIO as
// TIME lines right on the second: once a minute, after NTP sets the clock, when the SCORPIO says HELLO, when the
// zone changes, and when the offset changes (daylight saving starts or ends).
#pragma once

#include <stdbool.h>
#include <stdint.h>

void clock_start(void);
void clock_send_now(void);                     // send TIME at the next second
bool clock_local(int64_t* local, bool* dst);   // local time (seconds since 1970), if the time is known
const char* clock_source(void);                // "ntp", "fake" (console testing) or "none" (not set yet)
void clock_fake(int64_t utc);                  // testing: set the clock to this UTC time and stop NTP
void clock_ntp(void);                          // back to NTP

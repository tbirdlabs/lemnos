// WiFi. With no network saved (or the saved one not found within 20 s) the radio opens its own setup network,
// "Salient-XXXX", whose captive portal shows the settings page; once on the home network it's reachable as
// http://salient.local (mDNS) and the setup network closes a minute later.
#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    bool connected;                    // on the home network
    char ssid[33];                     // the home network's name (saved), "" if none
    char ip[16];                       // the home network address, "" if not connected
    int rssi;
    bool ap_on;                        // the setup network is open
    char ap_ssid[20];                  // "Salient-XXXX"
} net_status_t;

typedef struct {
    char ssid[33];
    int8_t rssi;
    bool open;
} net_seen_t;

void net_start(void);
void net_status(net_status_t* s);
int net_scan(net_seen_t* out, int max);      // networks in range, strongest first (takes ~2 s)
void net_restart_soon(void);                 // restart in a moment (after the web reply goes out)
void net_forget_wifi(void);                  // clear the saved network and restart into setup
bool net_ap_active(void);

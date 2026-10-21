#include "display.h"

#include "board.h"

#if !BOARD_DISPLAY

void display_start(void) {}

#else

#include <stdio.h>
#include <string.h>

#include "bt.h"
#include "clock.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_log.h"
#include "font8x8.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "hub.h"
#include "net.h"
#include "tz.h"

#define W 240                          // landscape
#define H 135
#define SCALE 2                        // 8x8 font at 2x: 15 characters a row
#define ROW_H (8 * SCALE)
#define ROWS 7
#define PITCH 19                       // rows 19 px apart
#define COLS (W / (8 * SCALE))

static const char* TAG = "display";

// RGB565, bytes swapped for the SPI transfer
#define RGB(r, g, b) ((uint16_t)((((r) & 0xF8) << 8 | ((g) & 0xFC) << 3 | (b) >> 3) >> 8 | \
                                 (((r) & 0xF8) << 8 | ((g) & 0xFC) << 3 | (b) >> 3) << 8))
#define BLACK RGB(0, 0, 0)
#define WHITE RGB(230, 230, 230)
#define AMBER RGB(255, 176, 0)
#define CYAN RGB(0, 220, 255)
#define GREEN RGB(60, 220, 90)
#define GREY RGB(130, 130, 130)
#define RED RGB(255, 70, 50)

static esp_lcd_panel_handle_t panel;
static SemaphoreHandle_t done;
static uint16_t buf[W * ROW_H];
static char shown[ROWS][COLS + 1];
static uint16_t shown_fg[ROWS];

static bool on_done(esp_lcd_panel_io_handle_t io, esp_lcd_panel_io_event_data_t* e, void* ctx) {
    (void)io;
    (void)e;
    BaseType_t woke = pdFALSE;
    xSemaphoreGiveFromISR((SemaphoreHandle_t)ctx, &woke);
    return woke == pdTRUE;
}

static void draw_row(int row, const char* text, uint16_t fg) {
    char t[COLS + 1];
    snprintf(t, sizeof(t), "%-*s", COLS, text);
    if (strcmp(t, shown[row]) == 0 && fg == shown_fg[row])
        return;
    strcpy(shown[row], t);
    shown_fg[row] = fg;
    for (int i = 0; i < W * ROW_H; i++)
        buf[i] = BLACK;
    for (int c = 0; c < COLS; c++) {
        unsigned ch = (unsigned char)t[c];
        if (ch < 32 || ch > 126)
            ch = '?';
        const uint8_t* g = font8x8[ch - 32];
        for (int gy = 0; gy < 8; gy++)
            for (int gx = 0; gx < 8; gx++)
                if (g[gy] >> gx & 1)
                    for (int sy = 0; sy < SCALE; sy++)
                        for (int sx = 0; sx < SCALE; sx++)
                            buf[(gy * SCALE + sy) * W + c * 8 * SCALE + gx * SCALE + sx] = fg;
    }
    int y = 1 + row * PITCH;
    esp_lcd_panel_draw_bitmap(panel, 0, y, W, y + ROW_H, buf);
    xSemaphoreTake(done, pdMS_TO_TICKS(200));          // buf is in use until the transfer is done
}

static const char* short_kind(int kind) {
    switch (kind) {
        case KIND_WIIMOTE:
            return "Wii";
        case KIND_XBOX:
            return "Xbox";
        case KIND_XAC:
            return "XAC";
        case KIND_PHONE:
            return "Phone";
        default:
            return "Pad";
    }
}

static void refresh(bool blink) {
    // every row fits COLS (15) characters; only a long home network name gets cut
    char l[40];
    int64_t local;
    bool dst;
    net_status_t ns;
    net_status(&ns);
    if (ns.ap_on && !ns.connected) {
        draw_row(0, "Join WiFi:", AMBER);
    } else if (clock_local(&local, &dst)) {
        int y, mo, d, h, mi, s;
        tz_civil(local, &y, &mo, &d, &h, &mi, &s);
        snprintf(l, sizeof(l), "Salient   %02d:%02d", h, mi);
        draw_row(0, l, AMBER);
    } else {
        draw_row(0, "Salient radio", AMBER);
    }

    if (ns.connected) {
        draw_row(1, "salient.local", WHITE);
        draw_row(2, ns.ip, GREY);
    } else if (ns.ap_on) {
        draw_row(1, ns.ap_ssid, CYAN);                  // "Salient-D531": the setup network, on a row of its own
        draw_row(2, "192.168.4.1", GREY);
    } else {
        draw_row(1, "Joining WiFi", GREY);
        draw_row(2, ns.ssid, GREY);
    }

    int left = bt_pairing_left();
    if (left) {
        snprintf(l, sizeof(l), "PAIRING %ds", left);
        draw_row(3, l, blink ? CYAN : WHITE);
    } else {
        hub_lock();
        if (hub_board.seen && hub_board.game[0])
            snprintf(l, sizeof(l), "%s", hub_board.game);   // the game running ("testpattern" is 11)
        else
            snprintf(l, sizeof(l), "%s", hub_board.seen ? "Board ok" : "No board yet");
        hub_unlock();
        draw_row(3, l, hub_board.seen ? GREEN : RED);
    }

    // who's playing: two to a row
    char rows[3][COLS + 1] = {"", "", ""};
    int n = 0;
    hub_lock();
    for (int s = 1; s <= KNOWN_SLOTS && n < 6; s++) {
        int i = hub_known.live[s];
        if (i < 0)
            continue;
        char p[12];
        snprintf(p, sizeof(p), "%d:%-5s ", s, short_kind(hub_known.k[i].kind));
        strncat(rows[n / 2], p, COLS - strlen(rows[n / 2]));
        n++;
    }
    hub_unlock();
    if (!n)
        draw_row(4, left ? "Pair a pad now" : "No players", GREY);
    for (int r = 0; r < 3; r++)
        if (n || r)
            draw_row(4 + r, rows[r], WHITE);
}

static void display_task(void* arg) {
    (void)arg;
    bool blink = false;
    for (;;) {
        refresh(blink);
        blink = !blink;
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

void display_start(void) {
    gpio_reset_pin(DISPLAY_BL);
    gpio_set_direction(DISPLAY_BL, GPIO_MODE_OUTPUT);
    gpio_set_level(DISPLAY_BL, 1);

    spi_bus_config_t bus = {
        .mosi_io_num = DISPLAY_MOSI,
        .sclk_io_num = DISPLAY_SCLK,
        .miso_io_num = -1,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = W * ROW_H * 2 + 8,
    };
    if (spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_CH_AUTO) != ESP_OK) {
        ESP_LOGE(TAG, "no SPI bus for the display");
        return;
    }
    done = xSemaphoreCreateBinary();
    esp_lcd_panel_io_handle_t io;
    esp_lcd_panel_io_spi_config_t ioc = {
        .dc_gpio_num = DISPLAY_DC,
        .cs_gpio_num = DISPLAY_CS,
        .pclk_hz = 40 * 1000 * 1000,
        .lcd_cmd_bits = 8,
        .lcd_param_bits = 8,
        .spi_mode = 0,
        .trans_queue_depth = 4,
        .on_color_trans_done = on_done,
        .user_ctx = done,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)SPI2_HOST, &ioc, &io));
    esp_lcd_panel_dev_config_t pc = {
        .reset_gpio_num = DISPLAY_RST,
        .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB,
        .bits_per_pixel = 16,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_st7789(io, &pc, &panel));
    esp_lcd_panel_reset(panel);
    esp_lcd_panel_init(panel);
    esp_lcd_panel_invert_color(panel, true);
    esp_lcd_panel_swap_xy(panel, true);                 // landscape (TFT_eSPI's rotation 1 on this board)
    esp_lcd_panel_mirror(panel, true, false);
    esp_lcd_panel_set_gap(panel, 40, 53);               // the 135x240 glass sits inside the controller's 240x320
    for (int i = 0; i < W * ROW_H; i++)
        buf[i] = BLACK;
    for (int y = 0; y < H; y += ROW_H) {
        int h = y + ROW_H > H ? H - y : ROW_H;
        esp_lcd_panel_draw_bitmap(panel, 0, y, W, y + h, buf);
        xSemaphoreTake(done, pdMS_TO_TICKS(200));
    }
    for (int r = 0; r < ROWS; r++)
        shown[r][0] = 1;                                // nothing matches: draw every row the first time
    esp_lcd_panel_disp_on_off(panel, true);
    xTaskCreate(display_task, "display", 3072, NULL, 2, NULL);
}

#endif

import gc
import time
import math
import board
import busio
import displayio
import supervisor
import terminalio
from rtc import RTC
from adafruit_bitmap_font import bitmap_font
from adafruit_matrixportal.network import Network
from adafruit_matrixportal.matrix import Matrix
import adafruit_display_text.label
import adafruit_imageload
import adafruit_lis3dh
from cedargrove_palettefader.palettefader import PaletteFader

# supervisor.disable_autoreload()

displayio.release_displays()

print("BOOT")

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# CONSTANTS ----------------------------------------------------------------

DEBUG = True
SPRITESHEET_FILENAME = "/sprites.bmp"

# CONFIGURABLE SETTINGS ----------------------------------------------------

BITPLANES = 6  # Ideally 6, but can set lower if RAM is tight
USE_NTP = True

# SOME UTILITY FUNCTIONS AND CLASSES ---------------------------------------


def build_rect(
    x, y, w, h, border=False, rounded=False, color_bg=None, color_border=0xFFFFFF
):
    # Create temporary bitmap and 2 color palette
    bitmap = displayio.Bitmap(w, h, 3)
    palette = displayio.Palette(3)
    palette.make_transparent(0)
    palette[0] = 0xFF00FF
    palette[1] = color_bg if color_bg is not None else 0x000000
    palette[2] = color_border
    # Fill background
    for by in range(h):
        for bx in range(w):
            bitmap[bx, by] = 1 if color_bg is not None else 0
    # Border
    if border:
        for bx in range(w):
            bitmap[bx, 0] = 2
            bitmap[bx, h - 1] = 2
        for by in range(h):
            bitmap[0, by] = 2
            bitmap[w - 1, by] = 2
    # Rounded corners
    if rounded:
        bitmap[0, 0] = 0
        bitmap[0, h - 1] = 0
        bitmap[w - 1, 0] = 0
        bitmap[w - 1, h - 1] = 0
    tilegrid = displayio.TileGrid(bitmap, pixel_shader=palette)
    tilegrid.x = x
    tilegrid.y = y
    return tilegrid


def build_sprite(
    spritesheet,
    palette,
    x,
    y,
    tile,
    w=1,
    h=1,
    tile_width=16,
    tile_height=16,
    brightness=0.1,
    gamma=1.0,
    normalize=True,
):
    palette.make_transparent(255)
    bitmap_faded = PaletteFader(palette, brightness, gamma, normalize)
    tilegrid = displayio.TileGrid(
        spritesheet,
        pixel_shader=bitmap_faded.palette,
        width=w,
        height=h,
        tile_width=tile_width,
        tile_height=tile_height,
        default_tile=tile,
    )
    tilegrid.x = x
    tilegrid.y = y
    return tilegrid


def build_bitmap(x, y, bitmap_file, brightness=0.1, gamma=1.0, normalize=True):
    bitmap, palette = adafruit_imageload.load(
        bitmap_file, bitmap=displayio.Bitmap, palette=displayio.Palette
    )
    bitmap_faded = PaletteFader(palette, brightness, gamma, normalize)
    tilegrid = displayio.TileGrid(bitmap, pixel_shader=bitmap_faded.palette)
    tilegrid.x = x
    tilegrid.y = y
    return tilegrid


def build_text(x, y, text, color=0xFFFFFF, font=terminalio.FONT):
    line = adafruit_display_text.label.Label(
        font=font, x=x, y=y, color=color, text=text
    )
    return line


def parse_time(timestring, is_dst=-1):
    # 2022-11-04 21:46:57.174 308 5 +0000 UTC
    bits = timestring.split(" ")
    year_month_day = bits[0].split("-")
    hour_minute_second = bits[1].split(":")
    return time.struct_time(
        (
            int(year_month_day[0]),
            int(year_month_day[1]),
            int(year_month_day[2]),
            int(hour_minute_second[0]),
            int(hour_minute_second[1]),
            int(hour_minute_second[2].split(".")[0]),
            -1,
            -1,
            is_dst,
        )
    )


# ONE-TIME INITIALIZATION --------------------------------------------------

MATRIX = Matrix(bit_depth=BITPLANES)
DISPLAY = MATRIX.display
NETWORK = Network(status_neopixel=board.NEOPIXEL, debug=False)
RTC_INST = RTC()
ACCEL = adafruit_lis3dh.LIS3DH_I2C(busio.I2C(board.SCL, board.SDA), address=0x19)
_ = ACCEL.acceleration  # Dummy reading to blow out any startup residue

time.sleep(0.1)

DISPLAY.rotation = (
    int(
        (
            (math.atan2(-ACCEL.acceleration.y, -ACCEL.acceleration.x) + math.pi)
            / (math.pi * 2)
            + 0.875
        )
        * 4
    )
    % 4
) * 90

nes_font = bitmap_font.load_font("/nes.bdf")
bitocra_font = bitmap_font.load_font("/bitocra7.bdf")
spritesheet, palette = adafruit_imageload.load(SPRITESHEET_FILENAME)


# DISPLAYIO PRIMITIVES -----------------------------------------------------

SPRITE_MARIO_STILL = 0
SPRITE_MARIO_JUMP = 4
SPRITE_MARIO_WALK1 = 5
SPRITE_MARIO_WALK2 = 6
SPRITE_MARIO_WALK3 = 7

g_root = displayio.Group()

g_floor1 = displayio.Group()
t_floor1brick1 = build_sprite(spritesheet, palette, 0, 24, 1, w=2)
t_floor1brick2 = build_sprite(spritesheet, palette, 48, 24, 2)
g_floor1.append(t_floor1brick1)
g_floor1.append(t_floor1brick2)
g_floor1.x = 0

g_floor2 = displayio.Group()
t_floor2brick1 = build_sprite(spritesheet, palette, 0, 24, 2, w=2)
t_floor2brick2 = build_sprite(spritesheet, palette, 48, 24, 1)
g_floor2.append(t_floor2brick1)
g_floor2.append(t_floor2brick2)
g_floor2.x = 64

g_date = displayio.Group()
t_ddmmyyyy = build_text(64, 15, "", color=0x001100, font=nes_font)
g_date.append(t_ddmmyyyy)

g_actors = displayio.Group()
t_mario = build_sprite(spritesheet, palette, 0, 8, SPRITE_MARIO_STILL)
g_actors.append(t_mario)

g_clock = displayio.Group()
t_hhmmss = build_text(32, 3, "??:??:??", color=0x111111, font=bitocra_font)
g_clock.append(t_hhmmss)
# g_clock.append(build_text(42, 6, "00", color=0x111111, font=nes_font))

g_debug = displayio.Group()
t_debug = build_text(3, 3, "", color=0x111111, font=bitocra_font)
g_debug.append(t_debug)

g_root.append(g_floor1)
g_root.append(g_floor2)
g_root.append(g_date)
g_root.append(g_actors)
g_root.append(g_clock)
g_root.append(g_debug)

# MAIN LOOP ----------------------------------------------------------------

NOW = RTC_INST.datetime

last_ntp_check = None
gravity = 1.2
scene_count = 16  # 16 displays (16 x 64 cols)
frame = 0

new_second = None
new_minute = None
new_hour = None

mario_sprite_idx = 0
mario_y = mario_y_default = t_mario.y
mario_jump_height = 12
mario_is_walking = False
mario_is_jumping = False
mario_is_falling = False
date_is_moving = False

ddmmyyyy = "{:0>2d}/{:0>2d}/{:0>4d}".format(NOW.tm_mday, NOW.tm_mon, NOW.tm_year)
hhmmss = "{:0>2d}:{:0>2d}:{:0>2d}".format(NOW.tm_hour, NOW.tm_min, NOW.tm_sec)

DISPLAY.show(g_root)

gc.collect()

while True:

    ts = time.monotonic()
    NOW = RTC_INST.datetime
    scene_frame = frame % DISPLAY.width
    scene_index = frame // DISPLAY.width

    if USE_NTP:
        if last_ntp_check is None or time.monotonic() > last_ntp_check + 3600:
            try:
                gc.collect()
                ntp_time = NETWORK.get_local_time()
                print("NTP Time", ntp_time)
                NOW = parse_time(ntp_time)
                RTC_INST.datetime = NOW
                ddmmyyyy = "{:0>2d}/{:0>2d}/{:0>4d}".format(
                    NOW.tm_mday, NOW.tm_mon, NOW.tm_year
                )
                last_ntp_check = time.monotonic()
            except Exception as e:
                print("NTP Error, retrying...", e)

    if new_second is None or ts > new_second + 1:
        # print("NEW SECOND", new_second)
        new_second = int(ts)
        hhmmss = "{:0>2d}:{:0>2d}:{:0>2d}".format(NOW.tm_hour, NOW.tm_min, NOW.tm_sec)
        t_hhmmss.text = hhmmss

        if new_minute is None or NOW.tm_sec == 0:
            # print("NEW MINUTE", new_minute)
            new_minute = ts

            if new_hour is None or NOW.tm_min == 0:
                # print("NEW HOUR", new_hour)
                ddmmyyyy = "{:0>2d}/{:0>2d}/{:0>4d}".format(
                    NOW.tm_mday, NOW.tm_mon, NOW.tm_year
                )
                t_ddmmyyyy.text = ddmmyyyy
                new_hour = ts

    # Render/print debugging info
    if DEBUG:
        pass
        # t_debug.text = "{:02d} {:02d}".format(scene_index, scene_frame)

    ### MARIO HANDLING ###

    # Trigger Mario Jump
    if mario_is_walking and scene_frame == 24:
        if not mario_is_jumping:
            mario_is_falling = False
            mario_is_jumping = True

    # Perform Mario Jump
    if mario_is_jumping and not mario_is_falling:
        mario_is_falling = True
        mario_y = mario_y - mario_jump_height

    # Apply Gravity
    if mario_is_falling:
        mario_y = mario_y + gravity

    # Peform Mario Landing
    if mario_y > mario_y_default:
        mario_y = mario_y_default
        mario_is_falling = False
        mario_is_jumping = False

    # Start Mario walking if not already after one scene
    if not mario_is_walking and scene_index >= 1:
        mario_is_walking = True

    # Animate Mario sprite (every 4th frame)
    if frame % 4 == 0:
        mario_sprite_idx = mario_sprite_idx + 1
        if mario_sprite_idx > 2:
            mario_sprite_idx = 0

    # Render Mario sprite
    t_mario.y = int(mario_y)
    if mario_is_jumping:
        t_mario[0] = SPRITE_MARIO_JUMP
    elif mario_is_walking:
        t_mario[0] = SPRITE_MARIO_WALK1 + mario_sprite_idx
    else:
        t_mario[0] = SPRITE_MARIO_STILL

    ### DATE HANDLING ###

    # Trigger date scroller
    if mario_is_walking and scene_index % 8 == 0 and scene_frame == 0:
        if not date_is_moving:
            date_is_moving = True

    if mario_is_walking and date_is_moving:
        if t_ddmmyyyy.x <= -DISPLAY.width - 64:
            t_ddmmyyyy.x = DISPLAY.width
            date_is_moving = False
        else:
            t_ddmmyyyy.x = t_ddmmyyyy.x - 1

    ### FLOOR HANDLING ###

    # Scroll floors to left
    if mario_is_walking:
        if g_floor1.x <= -DISPLAY.width:
            g_floor1.x = DISPLAY.width - 1
        else:
            g_floor1.x = g_floor1.x - 1

        if g_floor2.x <= -DISPLAY.width:
            g_floor2.x = DISPLAY.width - 1
        else:
            g_floor2.x = g_floor2.x - 1

    ### END OF FRAME ###

    # Increment frame index
    if frame >= (DISPLAY.width * scene_count) - 1:
        frame = 0
    else:
        frame = frame + 1

    time.sleep(0.02)

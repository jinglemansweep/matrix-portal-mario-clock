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
USE_NTP = False

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

g_actors = displayio.Group()
t_mario = build_sprite(spritesheet, palette, 0, 8, SPRITE_MARIO_STILL)
g_actors.append(t_mario)

g_clock = displayio.Group()
t_hhmmss = build_text(32, 3, "??:??:??", color=0x111111, font=bitocra_font)
g_clock.append(t_hhmmss)
# g_clock.append(build_text(42, 6, "00", color=0x111111, font=nes_font))

g_debug = displayio.Group()
t_debug = build_text(3, 3, "xxx", color=0x111111, font=bitocra_font)
g_debug.append(t_debug)

g_root.append(g_floor1)
g_root.append(g_floor2)
g_root.append(g_actors)
g_root.append(g_clock)
g_root.append(g_debug)

# MAIN LOOP ----------------------------------------------------------------

last_ntp_check = None
frame = 0
mario_sprite_idx = 0
gravity = 1
mario_y_default = t_mario.y
mario_jump_height = 9
mario_is_jumping = False
mario_is_falling = False

DISPLAY.show(g_root)

gc.collect()

while True:

    NOW = RTC_INST.datetime

    if USE_NTP:
        if last_ntp_check is None or time.monotonic() > last_ntp_check + 3600:
            try:
                gc.collect()
                ntp_time = NETWORK.get_local_time()
                print("NTP Time", ntp_time)
                RTC_INST.datetime = parse_time(ntp_time)
                last_ntp_check = time.monotonic()
            except Exception as e:
                print("NTP Error, retrying...", e)

    hhmmss = "{:0>2d}:{:0>2d}:{:0>2d}".format(NOW.tm_hour, NOW.tm_min, NOW.tm_sec)
    t_hhmmss.text = hhmmss

    t_debug.text = "{}".format(frame % 64)

    # Render Mario sprite
    if mario_is_jumping:
        t_mario[0] = SPRITE_MARIO_JUMP
    else:
        t_mario[0] = SPRITE_MARIO_WALK1 + mario_sprite_idx

    # Trigger Mario Jump
    if frame % 64 == 28:
        if not mario_is_jumping:
            mario_is_falling = False
            mario_is_jumping = True

    # Perform Mario Jump
    if mario_is_jumping and not mario_is_falling:
        mario_is_falling = True
        t_mario.y = t_mario.y - mario_jump_height

    # Apply Gravity
    if mario_is_falling:
        t_mario.y = int(t_mario.y + gravity)

    # Peform Mario Landing
    if t_mario.y > mario_y_default:
        t_mario.y = mario_y_default
        mario_is_falling = False
        mario_is_jumping = False

    # Animate Mario sprite (every 4th frame)
    if frame % 4 == 0:
        mario_sprite_idx = mario_sprite_idx + 1
        if mario_sprite_idx > 2:
            mario_sprite_idx = 0

    # Scroll floors to left
    if g_floor1.x <= -DISPLAY.width:
        g_floor1.x = DISPLAY.width - 1
    else:
        g_floor1.x = g_floor1.x - 1

    if g_floor2.x <= -DISPLAY.width:
        g_floor2.x = DISPLAY.width - 1
    else:
        g_floor2.x = g_floor2.x - 1

    # Increment frame index
    if frame >= (DISPLAY.width * 4) - 1:
        frame = 0
    else:
        frame = frame + 1

    # time.sleep(0.01 * ((60 - NOW.tm_sec) / 10))

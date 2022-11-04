import gc
import random
import time
import math
import board
import busio
import displayio
import terminalio
import supervisor
from rtc import RTC
import adafruit_imageload
from adafruit_matrixportal.network import Network
from adafruit_matrixportal.matrix import Matrix
from adafruit_bitmap_font import bitmap_font
import adafruit_display_text.label
import adafruit_lis3dh
from cedargrove_palettefader.palettefader import PaletteFader

# supervisor.disable_autoreload()

print("BOOT")

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# CONFIGURABLE SETTINGS ----------------------------------------------------

BITPLANES = 6  # Ideally 6, but can set lower if RAM is tight

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


def build_sprites(
    x,
    y,
    bitmap_file,
    w,
    h,
    tile,
    tile_width=16,
    tile_height=16,
    brightness=0.1,
    gamma=1.0,
    normalize=True,
):
    bitmap, palette = adafruit_imageload.load(
        bitmap_file, bitmap=displayio.Bitmap, palette=displayio.Palette
    )
    palette.make_transparent(255)
    bitmap_faded = PaletteFader(palette, brightness, gamma, normalize)
    tilegrid = displayio.TileGrid(
        bitmap,
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


# ONE-TIME INITIALIZATION --------------------------------------------------

MATRIX = Matrix(bit_depth=BITPLANES)
DISPLAY = MATRIX.display
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

root_group = displayio.Group()

group1 = displayio.Group()
group1.append(build_sprites(0, 8, "/sprites.bmp", 1, 1, 0))
group1.append(build_sprites(0, 24, "/sprites.bmp", 2, 1, 1))
group1.append(build_sprites(48, 24, "/sprites.bmp", 1, 1, 2))

group1.append(
    build_rect(
        30,
        1,
        33,
        12,
        border=True,
        rounded=True,
        color_bg=0x070000,
        color_border=0x111100,
    )
)
group1.append(build_text(32, 6, "00:00", color=0x111111))

root_group.append(group1)

# NETWORK = Network(status_neopixel=board.NEOPIXEL, debug=False)
# NETWORK.connect()

# MAIN LOOP ----------------------------------------------------------------

tick = 0
DISPLAY.show(root_group)

bg_x, bg_y = root_group[0][0].x, root_group[0][0].y

while True:
    gc.collect()
    NOW = time.time()
    # root_group[0][3].text = "{0:9d}".format(tick)
    # root_group[0][0].x = bg_x + random.choice([-1, 1])
    # root_group[0][0].y = bg_y + random.choice([-1, 1])
    # DISPLAY.refresh()
    tick = tick + 1

import gc
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


def build_rect(x, y, w, h, border=False, color_bg=0x000000, color_border=0xFFFFFF):
    # Create temporary bitmap and 2 color palette
    bitmap = displayio.Bitmap(w, h, 2)
    palette = displayio.Palette(2)
    palette[0] = color_bg
    palette[1] = color_border
    # Fill background
    for by in range(h):
        for bx in range(w):
            bitmap[bx, by] = 0
    # Border
    if border:
        for bx in range(w):
            bitmap[bx, 0] = 1
            bitmap[bx, h - 1] = 1
        for by in range(h):
            bitmap[0, by] = 1
            bitmap[w - 1, by] = 1
    tilegrid = displayio.TileGrid(bitmap, pixel_shader=palette)
    tilegrid.x = x
    tilegrid.y = y
    return tilegrid


def build_bitmap(bitmap_file, brightness=0.1, gamma=1.0, normalize=True):
    bitmap, palette = adafruit_imageload.load(
        bitmap_file, bitmap=displayio.Bitmap, palette=displayio.Palette
    )
    bitmap_faded = PaletteFader(palette, brightness, gamma, normalize)
    tilegrid = displayio.TileGrid(bitmap, pixel_shader=bitmap_faded.palette)
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
# group1.append(build_bitmap("photos/louis-closeup.bmp"))
group1.append(build_rect(0, 0, 64, 32, color_bg=0x080000))
group1.append(build_rect(2, 4, 60, 12, border=True, color_border=0x111100))
group1.append(build_text(5, 9, "HISS HISS", color=0x111111))

root_group.append(group1)

# NETWORK = Network(status_neopixel=board.NEOPIXEL, debug=False)
# NETWORK.connect()

# MAIN LOOP ----------------------------------------------------------------

while True:
    gc.collect()
    NOW = time.time()
    DISPLAY.show(root_group)
    DISPLAY.refresh()
    time.sleep(2)

# SPDX-FileCopyrightText: 2020 Phillip Burgess for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
MOON PHASE CLOCK for Adafruit Matrix Portal: displays current time, lunar
phase and time of next moonrise or moonset. Requires WiFi internet access.

Written by Phil 'PaintYourDragon' Burgess for Adafruit Industries.
MIT license, all text above must be included in any redistribution.

BDF fonts from the X.Org project. Startup 'splash' images should not be
included in derivative projects, thanks. Tall splash images licensed from
123RF.com, wide splash images used with permission of artist Lew Lashmit
(viergacht@gmail.com). Rawr!
"""

# pylint: disable=import-error
import gc
import time
import math
import board
import busio
import displayio
import supervisor
from rtc import RTC
from adafruit_matrixportal.network import Network
from adafruit_matrixportal.matrix import Matrix
from adafruit_bitmap_font import bitmap_font
import adafruit_display_text.label
import adafruit_lis3dh

# supervisor.disable_autoreload()

try:
    from secrets import secrets
except ImportError:
    print('WiFi secrets are kept in secrets.py, please add them there!')
    raise

# CONFIGURABLE SETTINGS ----------------------------------------------------

TWELVE_HOUR = False # If set, use 12-hour time vs 24-hour (e.g. 3:00 vs 15:00)
COUNTDOWN = False  # If set, show time to (vs time of) next rise/set event
MONTH_DAY = True   # If set, use MM/DD vs DD/MM (e.g. 31/12 vs 12/31)
BITPLANES = 6      # Ideally 6, but can set lower if RAM is tight


# SOME UTILITY FUNCTIONS AND CLASSES ---------------------------------------

def build_bitmap_group(bitmap_file):
    group = displayio.Group()
    bitmap = displayio.OnDiskBitmap(open(bitmap_file, 'rb'))
    tile_grid = displayio.TileGrid(
        bitmap,
        pixel_shader=getattr(bitmap, 'pixel_shader', displayio.ColorConverter())
    )
    group.append(tile_grid)
    return group

# ONE-TIME INITIALIZATION --------------------------------------------------

MATRIX = Matrix(bit_depth=BITPLANES)
DISPLAY = MATRIX.display
ACCEL = adafruit_lis3dh.LIS3DH_I2C(busio.I2C(board.SCL, board.SDA),
                                   address=0x19)
_ = ACCEL.acceleration # Dummy reading to blow out any startup residue
time.sleep(0.1)
DISPLAY.rotation = (int(((math.atan2(-ACCEL.acceleration.y,
                                     -ACCEL.acceleration.x) + math.pi) /
                         (math.pi * 2) + 0.875) * 4) % 4) * 90

LARGE_FONT = bitmap_font.load_font('/fonts/helvB12.bdf')
SMALL_FONT = bitmap_font.load_font('/fonts/helvR10.bdf')
SYMBOL_FONT = bitmap_font.load_font('/fonts/6x10.bdf')
LARGE_FONT.load_glyphs('0123456789:')
SMALL_FONT.load_glyphs('0123456789:/.%')
SYMBOL_FONT.load_glyphs('\u21A5\u21A7')

slides = [
    build_bitmap_group('/dogs.bmp'),
    build_bitmap_group('/louis.bmp'),
    build_bitmap_group('/couple.bmp'),
]
  
# NETWORK = Network(status_neopixel=board.NEOPIXEL, debug=False)
# NETWORK.connect()

# MAIN LOOP ----------------------------------------------------------------

while True:
    gc.collect()
    NOW = time.time()
    for slide in slides:
        DISPLAY.show(slide)
        DISPLAY.refresh()
        time.sleep(2)

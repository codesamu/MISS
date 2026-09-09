#!/usr/bin/env python3

import time
from rpi_ws281x import PixelStrip, Color

# Configuration
LED_COUNT = 6      # Change to your actual number of LEDs
LED_PIN = 12        # GPIO12
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 255
LED_INVERT = False
LED_CHANNEL = 0

# Create strip object
strip = PixelStrip(
    LED_COUNT,
    LED_PIN,
    LED_FREQ_HZ,
    LED_DMA,
    LED_INVERT,
    LED_BRIGHTNESS,
    LED_CHANNEL
)

strip.begin()

# Set all LEDs to white
for i in range(strip.numPixels()):
    strip.setPixelColor(i, Color(255, 255, 255))

strip.show()

print("LED strip set to white.")

# Keep program running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    # Turn LEDs off when exiting
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()

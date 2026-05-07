#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import time
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

import st7796
import ft6336u

# ========================================
# Configuration
# ========================================

APP_DIR = Path(__file__).resolve().parent
LCD_WIDTH = 480
LCD_HEIGHT = 320
HEADER_H = 46
TOUCH_TIMEOUT = 0.05

# Fonts
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_PATH_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_LARGE = ImageFont.truetype(FONT_PATH_BOLD, 24)
FONT_MEDIUM = ImageFont.truetype(FONT_PATH, 18)
FONT_SMALL = ImageFont.truetype(FONT_PATH, 13)

# Colors
C_BG = (18, 18, 18)
C_SURFACE = (35, 35, 45)
C_PRIMARY = (41, 98, 255)
C_SUCCESS = (30, 190, 90)
C_DANGER = (220, 50, 50)
C_MUTED = (120, 120, 135)
C_WHITE = (255, 255, 255)
C_HEADER = (25, 25, 40)

# ========================================
# UI Helpers
# ========================================

def new_screen(bg=C_BG):
    return Image.new('RGB', (LCD_WIDTH, LCD_HEIGHT), color=bg)

def draw_header(image, title):
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, LCD_WIDTH, HEADER_H], fill=C_HEADER)
    draw.rectangle([0, HEADER_H, LCD_WIDTH, HEADER_H + 2], fill=C_PRIMARY)
    bbox = draw.textbbox((0, 0), title, font=FONT_LARGE)
    tx = (LCD_WIDTH - (bbox[2] - bbox[0])) // 2
    ty = (HEADER_H - (bbox[3] - bbox[1])) // 2
    draw.text((tx, ty), title, font=FONT_LARGE, fill=C_WHITE)

def draw_rounded_rect(draw, x, y, w, h, radius, fill):
    draw.rectangle([x + radius, y, x + w - radius, y + h], fill=fill)
    draw.rectangle([x, y + radius, x + w, y + h - radius], fill=fill)
    draw.ellipse([x, y, x + 2*radius, y + 2*radius], fill=fill)
    draw.ellipse([x + w - 2*radius, y, x + w, y + 2*radius], fill=fill)
    draw.ellipse([x, y + h - 2*radius, x + 2*radius, y + h], fill=fill)
    draw.ellipse([x + w - 2*radius, y + h - 2*radius, x + w, y + h], fill=fill)

class TouchButton:
    def __init__(self, x, y, w, h, text, bg=C_PRIMARY, fg=C_WHITE, font=None, radius=10):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.text = text
        self.bg = bg
        self.fg = fg
        self.font = font or FONT_MEDIUM
        self.radius = radius

    def is_touched(self, tx, ty):
        return self.x <= tx <= self.x + self.w and self.y <= ty <= self.y + self.h

    def draw(self, image):
        draw = ImageDraw.Draw(image)
        draw_rounded_rect(draw, self.x, self.y, self.w, self.h, self.radius, self.bg)
        bbox = draw.textbbox((0, 0), self.text, font=self.font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(
            (self.x + (self.w - tw) // 2, self.y + (self.h - th) // 2),
            self.text, font=self.font, fill=self.fg
        )

# ========================================
# Dashboard App
# ========================================

class DashboardApp:
    def __init__(self):
        print("Initializing Dashboard...")
        try:
            self.lcd = st7796.st7796()
            self.touch = ft6336u.ft6336u()
        except Exception as e:
            print(f"Hardware error: {e}")
            sys.exit(1)
        
        self.lcd.clear()
        print("Dashboard ready.")

    def _get_touch(self):
        self.touch.read_touch_data()
        result = self.touch.get_touch_xy()
        if result is None:
            return None
        point, coords = result
        if point != 0 and coords:
            px = coords[0]['x']
            py = coords[0]['y']
            lx = 479 - py
            ly = 319 - px
            return lx, ly
        return None

    def _wait_for_buttons(self, buttons):
        while True:
            xy = self._get_touch()
            if xy:
                for i, btn in enumerate(buttons):
                    if btn.is_touched(*xy):
                        time.sleep(0.12) # Debounce
                        return i
            time.sleep(TOUCH_TIMEOUT)

    def show_menu(self):
        img = new_screen()
        draw_header(img, "SmartBin Dashboard")
        draw = ImageDraw.Draw(img)
        draw.text((12, HEADER_H + 10), "Select application to start", font=FONT_SMALL, fill=C_MUTED)

        BW, BH = 400, 70
        ox = (LCD_WIDTH - BW) // 2
        oy_start = HEADER_H + 40
        gap = 20

        buttons = [
            TouchButton(ox, oy_start, BW, BH, "Camera", bg=C_PRIMARY),
            TouchButton(ox, oy_start + BH + gap, BW, BH, "Servo Control", bg=C_SUCCESS),
            TouchButton(ox, oy_start + 2*(BH + gap), BW, 42, "Exit Dashboard", bg=C_DANGER),
        ]

        for btn in buttons:
            btn.draw(img)
        
        self.lcd.show_image(img)

        idx = self._wait_for_buttons(buttons)
        if idx == 0:
            self.launch_script("main.py")
        elif idx == 1:
            self.launch_script("display-servos.py")
        elif idx == 2:
            raise KeyboardInterrupt()

    def launch_script(self, script_name):
        script_path = APP_DIR / script_name
        print(f"Launching {script_path}...")
        
        # Clear screen before launching to indicate transition
        self.lcd.clear()
        
        try:
            # Run the script and wait for it to finish
            subprocess.run(["python3", str(script_path)], check=False)
        except Exception as e:
            print(f"Error launching {script_name}: {e}")
        
        print(f"{script_name} finished. Returning to dashboard.")
        # Re-clear if needed or just redraw
        self.lcd.clear()

    def run(self):
        try:
            while True:
                self.show_menu()
        except KeyboardInterrupt:
            print("\nDashboard exiting.")
        finally:
            self.lcd.clear()

if __name__ == "__main__":
    app = DashboardApp()
    app.run()

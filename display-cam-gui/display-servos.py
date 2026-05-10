#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import time
from gpiozero import Servo
from PIL import Image, ImageDraw, ImageFont

import ft6336u
import st7796

# ========================================
# Display / UI config
# ========================================

LCD_WIDTH = 480
LCD_HEIGHT = 320
HEADER_H = 46
TOUCH_TIMEOUT = 0.05

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_PATH_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_LARGE = ImageFont.truetype(FONT_PATH_BOLD, 24)
FONT_MEDIUM = ImageFont.truetype(FONT_PATH, 18)
FONT_SMALL = ImageFont.truetype(FONT_PATH, 13)

C_BG = (18, 18, 18)
C_SURFACE = (35, 35, 45)
C_PRIMARY = (41, 98, 255)
C_SUCCESS = (30, 190, 90)
C_DANGER = (220, 50, 50)
C_MUTED = (120, 120, 135)
C_WHITE = (255, 255, 255)
C_HEADER = (25, 25, 40)

# ========================================
# Servo config
# ========================================

servos = {
    "horizontal": Servo(16),
    "vertical": Servo(20),
}

directions = {
    "rf": {"horizontal": "min", "vertical": "min"},
    "lf": {"horizontal": "max", "vertical": "min"},
    "lb": {"horizontal": "min", "vertical": "max"},
    "rb": {"horizontal": "max", "vertical": "max"},
}

# ========================================
# UI helpers
# ========================================

def new_screen(bg=C_BG):
    return Image.new("RGB", (LCD_WIDTH, LCD_HEIGHT), color=bg)

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
    draw.ellipse([x, y, x + 2 * radius, y + 2 * radius], fill=fill)
    draw.ellipse([x + w - 2 * radius, y, x + w, y + 2 * radius], fill=fill)
    draw.ellipse([x, y + h - 2 * radius, x + 2 * radius, y + h], fill=fill)
    draw.ellipse([x + w - 2 * radius, y + h - 2 * radius, x + w, y + h], fill=fill)

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
        draw.text((self.x + (self.w - tw) // 2, self.y + (self.h - th) // 2), self.text, font=self.font, fill=self.fg)

# ========================================
# Servo display app
# ========================================

class ServoDisplayApp:
    def __init__(self):
        print("Initialisiere Servo Display...")
        try:
            self.lcd = st7796.st7796()
            self.touch = ft6336u.ft6336u()
        except Exception as e:
            print(f"Hardware-Fehler: {e}")
            sys.exit(1)

        self.status = "Ready"
        self.state = "main_menu"
        self.lcd.clear()
        self.center_all()

    def _get_touch(self):
        self.touch.read_touch_data()
        result = self.touch.get_touch_xy()
        if result is None:
            return None
        point, coords = result
        if point != 0 and coords:
            px = coords[0]["x"]
            py = coords[0]["y"]
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
                        time.sleep(0.12)
                        return i
            time.sleep(TOUCH_TIMEOUT)

    def center_all(self):
        for servo in servos.values():
            servo.mid()
        self.status = "All servos centered"
        time.sleep(0.2)

    def move_direction(self, key):
        mapping = directions.get(key)
        if not mapping:
            self.status = "Invalid direction"
            return

        for servo_name, position in mapping.items():
            getattr(servos[servo_name], position)()
            time.sleep(0.7)

        time.sleep(1.0)
        servos["vertical"].mid()
        time.sleep(0.7)
        servos["horizontal"].mid()
        time.sleep(0.7)
        self.status = f"Direction {key} done"

    def move_single(self, servo_name, position):
        getattr(servos[servo_name], position)()
        self.status = f"{servo_name} -> {position}"
        time.sleep(0.15)

    def _draw_footer_status(self, img):
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, LCD_HEIGHT - 28, LCD_WIDTH, LCD_HEIGHT], fill=C_SURFACE)
        draw.text((8, LCD_HEIGHT - 22), self.status, font=FONT_SMALL, fill=C_WHITE)

    def show_main_menu(self):
        self.state = "main_menu"
        img = new_screen()
        draw_header(img, "Servo Control")

        title = ImageDraw.Draw(img)
        title.text((12, HEADER_H + 10), "Choose control mode", font=FONT_SMALL, fill=C_MUTED)

        buttons = [
            TouchButton(40, 90, 400, 64, "Direction Control", bg=C_PRIMARY),
            TouchButton(40, 170, 400, 64, "Individual Servo", bg=C_SUCCESS),
            TouchButton(40, 250, 195, 42, "Center All", bg=C_MUTED),
            TouchButton(245, 250, 195, 42, "Exit", bg=C_DANGER),
        ]
        for btn in buttons:
            btn.draw(img)
        self._draw_footer_status(img)
        self.lcd.show_image(img)

        idx = self._wait_for_buttons(buttons)
        if idx == 0:
            self.show_direction_menu()
        elif idx == 1:
            self.show_individual_menu()
        elif idx == 2:
            self.center_all()
        elif idx == 3:
            raise KeyboardInterrupt()

    def show_direction_menu(self):
        self.state = "direction_menu"
        while True:
            img = new_screen()
            draw_header(img, "Direction Input")
            draw = ImageDraw.Draw(img)
            draw.text((12, HEADER_H + 8), "Like direction-input.py: lf / rf / lb / rb", font=FONT_SMALL, fill=C_MUTED)

            buttons = [
                TouchButton(85, 86, 140, 76, "LF", bg=C_PRIMARY),
                TouchButton(255, 86, 140, 76, "RF", bg=C_PRIMARY),
                TouchButton(85, 172, 140, 76, "LB", bg=C_PRIMARY),
                TouchButton(255, 172, 140, 76, "RB", bg=C_PRIMARY),
                TouchButton(8, 250, 120, 42, "Back", bg=C_MUTED),
                TouchButton(138, 250, 164, 42, "Center", bg=C_SUCCESS),
                TouchButton(312, 250, 160, 42, "Home", bg=C_MUTED),
            ]
            for btn in buttons:
                btn.draw(img)

            self._draw_footer_status(img)
            self.lcd.show_image(img)

            idx = self._wait_for_buttons(buttons)
            if idx == 0:
                self.move_direction("lf")
            elif idx == 1:
                self.move_direction("rf")
            elif idx == 2:
                self.move_direction("lb")
            elif idx == 3:
                self.move_direction("rb")
            elif idx == 4:
                return
            elif idx == 5:
                self.center_all()
            elif idx == 6:
                self.show_main_menu()
                return

    def show_individual_menu(self):
        self.state = "individual_menu"
        while True:
            img = new_screen()
            draw_header(img, "Individual Servo")
            draw = ImageDraw.Draw(img)
            draw.text((12, HEADER_H + 8), "Move each servo to min / mid / max", font=FONT_SMALL, fill=C_MUTED)

            row_y_1 = 90
            row_y_2 = 170
            col_w = 112
            gap = 8
            x0 = 8

            draw.text((8, row_y_1 - 18), "Horizontal", font=FONT_SMALL, fill=C_WHITE)
            draw.text((8, row_y_2 - 18), "Vertical", font=FONT_SMALL, fill=C_WHITE)

            buttons = [
                TouchButton(x0 + 0 * (col_w + gap), row_y_1, col_w, 62, "H Min", bg=C_PRIMARY),
                TouchButton(x0 + 1 * (col_w + gap), row_y_1, col_w, 62, "H Mid", bg=C_PRIMARY),
                TouchButton(x0 + 2 * (col_w + gap), row_y_1, col_w, 62, "H Max", bg=C_PRIMARY),
                TouchButton(x0 + 3 * (col_w + gap), row_y_1, col_w, 62, "Center", bg=C_SUCCESS),
                TouchButton(x0 + 0 * (col_w + gap), row_y_2, col_w, 62, "V Min", bg=C_PRIMARY),
                TouchButton(x0 + 1 * (col_w + gap), row_y_2, col_w, 62, "V Mid", bg=C_PRIMARY),
                TouchButton(x0 + 2 * (col_w + gap), row_y_2, col_w, 62, "V Max", bg=C_PRIMARY),
                TouchButton(x0 + 3 * (col_w + gap), row_y_2, col_w, 62, "Center", bg=C_SUCCESS),
                TouchButton(8, 250, 230, 42, "Back", bg=C_MUTED),
                TouchButton(242, 250, 230, 42, "Home", bg=C_MUTED),
            ]
            for btn in buttons:
                btn.draw(img)

            self._draw_footer_status(img)
            self.lcd.show_image(img)

            idx = self._wait_for_buttons(buttons)
            if idx == 0:
                self.move_single("horizontal", "min")
            elif idx == 1:
                self.move_single("horizontal", "mid")
            elif idx == 2:
                self.move_single("horizontal", "max")
            elif idx == 3:
                self.center_all()
            elif idx == 4:
                self.move_single("vertical", "min")
            elif idx == 5:
                self.move_single("vertical", "mid")
            elif idx == 6:
                self.move_single("vertical", "max")
            elif idx == 7:
                self.center_all()
            elif idx == 8:
                return
            elif idx == 9:
                self.show_main_menu()
                return

    def run(self):
        try:
            while True:
                self.show_main_menu()
        except KeyboardInterrupt:
            print("\nBeendet.")
        finally:
            self.center_all()
            self.lcd.clear()
            self.lcd.close()
            self.touch.close()

if __name__ == "__main__":
    app = ServoDisplayApp()
    app.run()

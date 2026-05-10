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
# Servo config (same direction style as direction-input.py)
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
            # portrait -> landscape (same mapping as existing app)
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
#!/usr/bin/python
# -*- coding: UTF-8 -*-

from gpiozero import Servo
from time import sleep


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


def center_all():
    """Move both servos to center."""
    for servo in servos.values():
        servo.mid()
    sleep(0.5)


def move_direction_mode():
    """
    Direction mode (same style as servo-test/direction-input.py):
    user enters lf/rf/lb/rb, servos move, then go back to center.
    """
    print("\nDirection mode")
    print("Commands: lf, rf, lb, rb")
    print("Type 'back' to return to menu.\n")

    while True:
        center_all()
        usr_inp = input("direction (l / r & f / b) (ex. lf): ").strip().lower()

        if usr_inp == "back":
            return

        if usr_inp in directions:
            for servo_name, position in directions[usr_inp].items():
                getattr(servos[servo_name], position)()
                print(f"{servo_name} -> {position}")
                sleep(1.0)

            print("sleep for trash to fall down")
            sleep(1.5)

            print("moving back")
            servos["vertical"].mid()
            print("vertical back")
            sleep(1.0)

            servos["horizontal"].mid()
            print("horizontal back")
            sleep(1.0)
        else:
            print("Falsche Eingabe, l/r & f/b eingeben.")


def move_single_servo_menu():
    """
    Individual servo movement menu.
    Lets you pick one servo and move it to min/mid/max.
    """
    print("\nIndividual servo movement")
    print("Servos: horizontal, vertical")
    print("Positions: min, mid, max")
    print("Type 'back' to return to menu.\n")

    while True:
        servo_name = input("servo (horizontal/vertical): ").strip().lower()
        if servo_name == "back":
            return
        if servo_name not in servos:
            print("Unknown servo. Use: horizontal or vertical")
            continue

        position = input("position (min/mid/max): ").strip().lower()
        if position == "back":
            return
        if position not in ("min", "mid", "max"):
            print("Unknown position. Use: min, mid or max")
            continue

        getattr(servos[servo_name], position)()
        print(f"{servo_name} moved to {position}")
        sleep(0.6)


def main_menu():
    print("\n=== Servo Control Menu ===")
    print("1) Direction control (lf/rf/lb/rb)")
    print("2) Individual servo movement")
    print("3) Center all servos")
    print("4) Exit")


def main():
    print("Servo control started.")
    center_all()

    while True:
        main_menu()
        choice = input("Select menu (1-4): ").strip().lower()

        if choice == "1":
            move_direction_mode()
        elif choice == "2":
            move_single_servo_menu()
        elif choice == "3":
            center_all()
            print("All servos centered.")
        elif choice == "4" or choice == "exit":
            center_all()
            print("Exiting.")
            break
        else:
            print("Invalid input. Please choose 1-4.")


if __name__ == "__main__":
    main()
#!/usr/bin/python
# -*- coding: UTF-8 -*-

import io
import json
import queue
import shutil
import sys
import threading
import time
import subprocess
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

import st7796
import ft6336u


# ========================================
# Konfiguration
# ========================================

APP_DIR       = Path(__file__).resolve().parent
DATA_DIR      = APP_DIR / "dataset"
SETTINGS_FILE = APP_DIR / "settings.json"

# LCD (Querformat / Landscape)
LCD_WIDTH  = 480
LCD_HEIGHT = 320
HEADER_H   = 46

TOUCH_TIMEOUT = 0.05

# Fonts
FONT_PATH      = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_PATH_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_LARGE  = ImageFont.truetype(FONT_PATH_BOLD, 24)
FONT_MEDIUM = ImageFont.truetype(FONT_PATH,      18)
FONT_SMALL  = ImageFont.truetype(FONT_PATH,      13)

# Farben
C_BG      = (18,  18,  18)
C_SURFACE = (35,  35,  45)
C_PRIMARY = (41,  98, 255)
C_SUCCESS = (30, 190,  90)
C_DANGER  = (220,  50,  50)
C_MUTED   = (120, 120, 135)
C_WHITE   = (255, 255, 255)
C_HEADER  = (25,  25,  40)

# Kategorien
LABELS = [
    ("Plastik",   "plastik"),
    ("Glas",      "glas"),
    ("Metall",    "metall"),
    ("Papier",    "papier"),
    ("Bio",       "bio"),
    ("Restmuell", "restmuell"),
    ("Elektro",   "elektro"),
    ("Textil",    "textil"),
    ("Sonstiges", "sonstiges"),
]


# ========================================
# UI-Hilfsfunktionen
# ========================================

def new_screen(bg=C_BG):
    """Neue leere Bildschirmfläche (480x320 Querformat)"""
    return Image.new('RGB', (LCD_WIDTH, LCD_HEIGHT), color=bg)


def draw_header(image, title):
    """Header-Leiste mit Trennlinie und zentriertem Titel"""
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, LCD_WIDTH, HEADER_H], fill=C_HEADER)
    draw.rectangle([0, HEADER_H, LCD_WIDTH, HEADER_H + 2], fill=C_PRIMARY)
    bbox = draw.textbbox((0, 0), title, font=FONT_LARGE)
    tx = (LCD_WIDTH - (bbox[2] - bbox[0])) // 2
    ty = (HEADER_H - (bbox[3] - bbox[1])) // 2
    draw.text((tx, ty), title, font=FONT_LARGE, fill=C_WHITE)


def draw_rounded_rect(draw, x, y, w, h, radius, fill, outline=None):
    """Rechteck mit abgerundeten Ecken"""
    draw.rectangle([x + radius, y, x + w - radius, y + h], fill=fill)
    draw.rectangle([x, y + radius, x + w, y + h - radius], fill=fill)
    draw.ellipse([x, y, x + 2*radius, y + 2*radius], fill=fill)
    draw.ellipse([x + w - 2*radius, y, x + w, y + 2*radius], fill=fill)
    draw.ellipse([x, y + h - 2*radius, x + 2*radius, y + h], fill=fill)
    draw.ellipse([x + w - 2*radius, y + h - 2*radius, x + w, y + h], fill=fill)
    if outline:
        draw.arc([x, y, x + 2*radius, y + 2*radius], 180, 270, fill=outline)
        draw.arc([x + w - 2*radius, y, x + w, y + 2*radius], 270, 360, fill=outline)
        draw.arc([x, y + h - 2*radius, x + 2*radius, y + h], 90, 180, fill=outline)
        draw.arc([x + w - 2*radius, y + h - 2*radius, x + w, y + h], 0, 90, fill=outline)
        draw.line([x + radius, y, x + w - radius, y], fill=outline)
        draw.line([x + radius, y + h, x + w - radius, y + h], fill=outline)
        draw.line([x, y + radius, x, y + h - radius], fill=outline)
        draw.line([x + w, y + radius, x + w, y + h - radius], fill=outline)


class TouchButton:
    """Touch-Button mit abgerundeten Ecken und zentriertem Text"""
    def __init__(self, x, y, w, h, text, bg=C_PRIMARY, fg=C_WHITE, font=None, radius=10):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.text = text
        self.bg   = bg
        self.fg   = fg
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


def ensure_data_dir():
    """Verzeichnisse für alle Kategorien anlegen"""
    for _, label_id in LABELS:
        (DATA_DIR / label_id).mkdir(parents=True, exist_ok=True)


def capture_rpicam(path, width=480, height=274, timeout_ms=500):
    """Einzelfoto mit rpicam-still aufnehmen"""
    subprocess.run(
        ['rpicam-still', '-o', str(path),
         '--width', str(width), '--height', str(height),
         '-n', '--timeout', str(timeout_ms)],
        check=False, timeout=15
    )


# ========================================
# Hauptanwendung
# ========================================

class SmartBinApp:
    def __init__(self):
        print("Initialisiere SmartBin (Querformat 480x320)...")
        try:
            self.lcd   = st7796.st7796()
            self.touch = ft6336u.ft6336u()
        except Exception as e:
            print(f"Hardware-Fehler: {e}")
            sys.exit(1)

        self.temp_path     = APP_DIR / "temp_preview.jpg"
        self.captured_path = APP_DIR / "temp_captured.jpg"
        self.state         = "main_menu"
        self.selected_idx  = None

        # Bildverarbeitungs-Einstellungen (Defaults)
        self.zoom        = 1.0
        self.center_x    = 0.0
        self.center_y    = 0.0
        self.brightness  = 0
        self.contrast    = 1.0
        self.saturation  = 1.0
        self.mirror      = False
        self.freeze      = False
        self.filter_mode = "normal"

        ensure_data_dir()
        self.load_settings()
        self.lcd.clear()
        print("Bereit.")

    # --------------------------------------------------
    # Touch – Querformat-Koordinatentransformation
    # Portrait-Touch: x=0..319, y=0..479
    # 90° CW Rotation: landscape_x = portrait_y
    #                  landscape_y = 319 - portrait_x
    # --------------------------------------------------
    def _get_touch(self):
        """Gibt (x, y) in Querformat-Koordinaten zurück, oder None"""
        self.touch.read_touch_data()
        result = self.touch.get_touch_xy()
        if result is None:
            return None
        point, coords = result
        if point != 0 and coords:
            px = coords[0]['x']   # Portrait x (0..319)
            py = coords[0]['y']   # Portrait y (0..479)
            # 90° CW: portrait top → landscape right
            lx = 479 - py         # Landscape x (0..479)
            ly = 319 - px         # Landscape y (0..319)
            return lx, ly
        return None

    def _wait_for_buttons(self, buttons):
        """Blockiert bis ein Button berührt wird. Gibt Index zurück."""
        while True:
            xy = self._get_touch()
            if xy:
                for i, btn in enumerate(buttons):
                    if btn.is_touched(*xy):
                        return i
            time.sleep(TOUCH_TIMEOUT)

    # --------------------------------------------------
    # Einstellungen laden / speichern
    # --------------------------------------------------
    def load_settings(self):
        try:
            if SETTINGS_FILE.exists():
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                self.zoom        = float(data.get("zoom",        self.zoom))
                self.center_x    = float(data.get("center_x",    self.center_x))
                self.center_y    = float(data.get("center_y",    self.center_y))
                self.brightness  = int(  data.get("brightness",  self.brightness))
                self.contrast    = float(data.get("contrast",    self.contrast))
                self.saturation  = float(data.get("saturation",  self.saturation))
                self.mirror      = bool( data.get("mirror",      self.mirror))
                self.freeze      = bool( data.get("freeze",      self.freeze))
                self.filter_mode = str(  data.get("filter_mode", self.filter_mode))
        except Exception as e:
            print(f"Einstellungen laden: {e}")

    def save_settings(self):
        try:
            SETTINGS_FILE.write_text(json.dumps({
                "zoom":        self.zoom,
                "center_x":    self.center_x,
                "center_y":    self.center_y,
                "brightness":  self.brightness,
                "contrast":    self.contrast,
                "saturation":  self.saturation,
                "mirror":      self.mirror,
                "freeze":      self.freeze,
                "filter_mode": self.filter_mode,
            }, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"Einstellungen speichern: {e}")

    # --------------------------------------------------
    # Bildverarbeitung
    # --------------------------------------------------
    def _apply_settings(self, frame):
        """Wendet Zoom, Pan, Helligkeit, Kontrast, Saettigung, Filter und Spiegel an"""
        img = frame
        w, h = img.size

        # Zoom + Pan (Crop + Resize)
        zoom = max(1.0, float(self.zoom))
        if zoom > 1.0:
            nw = max(1, int(w / zoom))
            nh = max(1, int(h / zoom))
            max_ox = max(0, (w - nw) // 2)
            max_oy = max(0, (h - nh) // 2)
            ox = int(w / 2 - nw / 2 + self.center_x * max_ox)
            oy = int(h / 2 - nh / 2 + self.center_y * max_oy)
            ox = max(0, min(w - nw, ox))
            oy = max(0, min(h - nh, oy))
            img = img.crop((ox, oy, ox + nw, oy + nh)).resize((w, h), Image.BILINEAR)

        # Helligkeit
        b_fac = 1.0 + self.brightness / 100.0
        if abs(b_fac - 1.0) > 0.01:
            img = ImageEnhance.Brightness(img).enhance(max(0.05, b_fac))

        # Kontrast
        if abs(self.contrast - 1.0) > 0.01:
            img = ImageEnhance.Contrast(img).enhance(self.contrast)

        # Saettigung
        if abs(self.saturation - 1.0) > 0.01:
            img = ImageEnhance.Color(img).enhance(self.saturation)

        # Filter
        if self.filter_mode == "gray":
            img = img.convert('L').convert('RGB')
        elif self.filter_mode == "blur":
            img = img.filter(ImageFilter.GaussianBlur(2))
        elif self.filter_mode == "sharpen":
            img = img.filter(ImageFilter.SHARPEN)
        elif self.filter_mode == "edges":
            img = img.filter(ImageFilter.FIND_EDGES).convert('RGB')
        elif self.filter_mode == "threshold":
            img = img.convert('L').point(lambda x: 255 if x > 120 else 0).convert('RGB')

        # Spiegeln
        if self.mirror:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)

        return img

    # --------------------------------------------------
    # Hauptmenü  –  3 Buttons nebeneinander
    # --------------------------------------------------
    def show_main_menu(self):
        self.state = "main_menu"
        img  = new_screen()
        draw_header(img, "SmartBin")
        draw = ImageDraw.Draw(img)
        draw.text((12, HEADER_H + 10), "Muelltrennung", font=FONT_SMALL, fill=C_MUTED)

        BW, BH = 146, 90
        GAP    = 10
        total_w = 3 * BW + 2 * GAP
        ox = (LCD_WIDTH - total_w) // 2
        oy = HEADER_H + 2 + (LCD_HEIGHT - HEADER_H - 2 - BH) // 2 + 8

        buttons = [
            TouchButton(ox,                oy, BW, BH, "Foto aufnehmen", bg=C_PRIMARY),
            TouchButton(ox + BW + GAP,     oy, BW, BH, "Statistiken",    bg=C_SUCCESS),
            TouchButton(ox + 2*(BW + GAP), oy, BW, BH, "Einstellungen",  bg=C_MUTED),
        ]
        for btn in buttons:
            btn.draw(img)
        self.lcd.show_image(img)

        idx = self._wait_for_buttons(buttons)
        if idx == 0:
            self.show_camera_view()
        elif idx == 1:
            self.show_stats()
        elif idx == 2:
            self.show_settings()

    # --------------------------------------------------
    # Kamera  –  MJPEG-Livestream via rpicam-vid
    # --------------------------------------------------
    def show_camera_view(self):
        self.state  = "camera"
        PREVIEW_H   = LCD_HEIGHT - 50
        BAR_Y       = PREVIEW_H

        back_btn    = TouchButton(8,   BAR_Y + 4, 130, 42, "Zurueck",   bg=C_MUTED)
        capture_btn = TouchButton(146, BAR_Y + 4, 326, 42, "Aufnehmen", bg=C_DANGER)

        frame_queue = queue.Queue(maxsize=2)
        proc = subprocess.Popen(
            ['rpicam-vid', '-t', '0', '--codec', 'mjpeg', '-o', '-',
             '--width', str(LCD_WIDTH), '--height', str(PREVIEW_H),
             '-n', '--framerate', '15'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )

        def _reader():
            buf = b''
            while True:
                chunk = proc.stdout.read(8192)
                if not chunk:
                    break
                buf += chunk
                while True:
                    start = buf.find(b'\xff\xd8')
                    end   = buf.find(b'\xff\xd9', start + 2) if start != -1 else -1
                    if start != -1 and end != -1:
                        jpeg = buf[start:end + 2]
                        buf  = buf[end + 2:]
                        try:
                            frame = Image.open(io.BytesIO(jpeg))
                            frame.load()
                            if frame_queue.full():
                                try: frame_queue.get_nowait()
                                except queue.Empty: pass
                            frame_queue.put_nowait(frame)
                        except Exception:
                            pass
                    else:
                        break

        threading.Thread(target=_reader, daemon=True).start()

        current    = None
        proc_alive = True
        try:
            while self.state == "camera":
                if not self.freeze:
                    try:
                        current = frame_queue.get(timeout=0.05)
                    except queue.Empty:
                        pass
                else:
                    time.sleep(0.05)

                if current is not None:
                    processed = self._apply_settings(current.resize((LCD_WIDTH, PREVIEW_H)))
                    img = new_screen()
                    img.paste(processed, (0, 0))
                    draw = ImageDraw.Draw(img)
                    draw.rectangle([0, PREVIEW_H, LCD_WIDTH, LCD_HEIGHT], fill=C_SURFACE)
                    back_btn.draw(img)
                    capture_btn.draw(img)
                    self.lcd.show_image(img)

                xy = self._get_touch()
                if xy:
                    if back_btn.is_touched(*xy):
                        break
                    if capture_btn.is_touched(*xy):
                        self._show_flash()
                        proc.terminate()
                        proc_alive = False
                        try: proc.wait(timeout=3)
                        except subprocess.TimeoutExpired: proc.kill()
                        capture_rpicam(self.captured_path, width=1920,
                                       height=1080, timeout_ms=1500)
                        self.show_review_screen()
                        return
        finally:
            if proc_alive:
                proc.terminate()
                try: proc.wait(timeout=3)
                except subprocess.TimeoutExpired: proc.kill()

    def _show_flash(self):
        """Kurzes weißes Aufleuchten als Auslöser-Feedback"""
        img = new_screen(C_WHITE)
        self.lcd.show_image(img)
        time.sleep(0.12)

    # --------------------------------------------------
    # Review  –  Foto links, Buttons rechts
    # --------------------------------------------------
    def show_review_screen(self):
        self.state = "review"
        if not self.captured_path.exists():
            self.show_main_menu()
            return

        img = new_screen()
        draw_header(img, "Foto pruefen")

        PHOTO_W = 280
        photo_h = LCD_HEIGHT - HEADER_H - 2
        photo   = Image.open(self.captured_path).resize((PHOTO_W, photo_h))
        img.paste(photo, (0, HEADER_H + 2))

        BX = PHOTO_W + 10
        BW = LCD_WIDTH - BX - 8

        cat_btn  = TouchButton(BX, HEADER_H + 18,  BW, 68, "Kategorie", bg=C_PRIMARY)
        back_btn = TouchButton(BX, HEADER_H + 100, BW, 58, "Zurueck",   bg=C_MUTED)
        cat_btn.draw(img)
        back_btn.draw(img)
        self.lcd.show_image(img)

        idx = self._wait_for_buttons([cat_btn, back_btn])
        if idx == 0:
            self.show_category_menu()
        else:
            self.show_camera_view()

    # --------------------------------------------------
    # Kategorie-Menü  –  3×3 Grid
    # --------------------------------------------------
    def show_category_menu(self):
        self.state = "category_menu"
        img = new_screen()
        draw_header(img, "Kategorie")

        BACK_H    = 44
        content_h = LCD_HEIGHT - HEADER_H - 2 - BACK_H - 6
        BW = (LCD_WIDTH - 4 * 8) // 3
        BH = (content_h - 2 * 6) // 3
        OX = 8
        OY = HEADER_H + 8

        buttons = []
        for i, (name, _) in enumerate(LABELS):
            col, row = i % 3, i // 3
            x = OX + col * (BW + 8)
            y = OY + row * (BH + 6)
            buttons.append(TouchButton(x, y, BW, BH, name, bg=C_PRIMARY, font=FONT_SMALL))

        for btn in buttons:
            btn.draw(img)

        back_btn = TouchButton(8, LCD_HEIGHT - BACK_H - 2, LCD_WIDTH - 16, BACK_H - 4,
                               "Zurueck", bg=C_MUTED)
        back_btn.draw(img)
        self.lcd.show_image(img)

        all_btns = buttons + [back_btn]
        idx = self._wait_for_buttons(all_btns)
        if idx == len(LABELS):
            self.show_review_screen()
        else:
            self.selected_idx = idx
            self.save_photo()

    # --------------------------------------------------
    # Foto speichern  –  mit Bestätigungs-Screen
    # --------------------------------------------------
    def save_photo(self):
        if not self.captured_path.exists() or self.selected_idx is None:
            self.show_main_menu()
            return

        label_name, label_id = LABELS[self.selected_idx]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = DATA_DIR / label_id / f"{label_id}_{timestamp}.jpg"
        # HD-Original direkt kopieren (keine Neukompression durch PIL-resize)
        shutil.copy2(self.captured_path, dest)
        print(f"Gespeichert (HD): {dest}")

        img  = new_screen()
        draw = ImageDraw.Draw(img)
        cx, cy = LCD_WIDTH // 2, LCD_HEIGHT // 2 - 28
        r = 52
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C_SUCCESS)
        draw.text((cx - 20, cy - 16), "OK", font=FONT_LARGE, fill=C_WHITE)

        bb = draw.textbbox((0, 0), label_name, font=FONT_LARGE)
        draw.text(((LCD_WIDTH - (bb[2]-bb[0])) // 2, cy + r + 8),
                  label_name, font=FONT_LARGE, fill=C_WHITE)

        bb2 = draw.textbbox((0, 0), "gespeichert", font=FONT_MEDIUM)
        draw.text(((LCD_WIDTH - (bb2[2]-bb2[0])) // 2, cy + r + 40),
                  "gespeichert", font=FONT_MEDIUM, fill=C_MUTED)
        self.lcd.show_image(img)
        time.sleep(2)

        self.selected_idx = None
        self.show_main_menu()

    # --------------------------------------------------
    # Statistiken  –  2-spaltig mit Balkendiagramm
    # --------------------------------------------------
    def show_stats(self):
        self.state = "stats"
        img  = new_screen()
        draw_header(img, "Statistiken")
        draw = ImageDraw.Draw(img)

        counts = [(name, lid, len(list((DATA_DIR / lid).glob("*.jpg"))))
                  for name, lid in LABELS]
        total  = sum(c for _, _, c in counts)
        max_c  = max(c for _, _, c in counts) or 1

        COL_W   = (LCD_WIDTH - 24) // 2
        BAR_MAX = COL_W - 90
        y0      = HEADER_H + 8
        ROW_H   = 26

        for i, (name, _, count) in enumerate(counts):
            col = i % 2
            row = i // 2
            x  = 8 + col * (COL_W + 8)
            ry = y0 + row * ROW_H
            bar_w = max(4, int(BAR_MAX * count / max_c))
            draw_rounded_rect(draw, x, ry, bar_w + 80, 22, 5, C_PRIMARY)
            draw.text((x + 4, ry + 4), f"{name}: {count}", font=FONT_SMALL, fill=C_WHITE)

        sep_y = y0 + 5 * ROW_H
        draw.rectangle([8, sep_y, LCD_WIDTH - 8, sep_y + 1], fill=C_MUTED)
        draw.text((8, sep_y + 5), f"Gesamt: {total}", font=FONT_MEDIUM, fill=C_WHITE)

        back_btn = TouchButton(8, LCD_HEIGHT - 48, LCD_WIDTH - 16, 40, "Zurueck", bg=C_MUTED)
        back_btn.draw(img)
        self.lcd.show_image(img)
        self._wait_for_buttons([back_btn])
        self.show_main_menu()

    # --------------------------------------------------
    # Einstellungen  –  vollständig
    # --------------------------------------------------
    def show_settings(self):
        self.state = "settings"

        FILTERS = [
            ("Normal",        "normal"),
            ("Grau",          "gray"),
            ("Weichzeichnen", "blur"),
            ("Schaerfen",     "sharpen"),
            ("Kanten",        "edges"),
            ("Threshold",     "threshold"),
        ]
        filt_names  = [f[0] for f in FILTERS]
        filt_values = [f[1] for f in FILTERS]

        # Reihen: (Attribut, Label, Min, Max, Schritt, Format)
        ROWS_NUM = [
            ("zoom",       "Zoom",       1.0,  3.0,  0.1,  "{:.1f}x"),
            ("center_x",   "Versatz X", -1.0,  1.0,  0.1,  "{:+.1f}" ),
            ("center_y",   "Versatz Y", -1.0,  1.0,  0.1,  "{:+.1f}" ),
            ("brightness", "Helligkeit",-100, 100,   10,   "{:+.0f}" ),
            ("contrast",   "Kontrast",   0.5,  2.0,  0.1,  "{:.1f}"  ),
            ("saturation", "Saettigung", 0.0,  2.0,  0.1,  "{:.1f}"  ),
        ]
        ROWS_BOOL = [
            ("mirror", "Spiegeln"),
            ("freeze", "Einfrieren"),
        ]
        n_num  = len(ROWS_NUM)
        n_bool = len(ROWS_BOOL)

        # Layout
        ROW_H   = 22
        ROW_STP = 24
        y0      = HEADER_H + 6
        LBL_W   = 110
        BTN_W   = 40
        VAL_W   = 76
        BTN1_X  = LBL_W + 6
        VAL_X   = BTN1_X + BTN_W + 4
        BTN2_X  = VAL_X + VAL_W + 4
        BOOL_W  = LCD_WIDTH - LBL_W - 14
        FBW     = 38
        FVW     = LCD_WIDTH - LBL_W - 14 - 2 * (FBW + 4)
        FX1     = LBL_W + 6
        FVX     = FX1 + FBW + 4
        FX2     = FVX + FVW + 4
        BOT_Y   = LCD_HEIGHT - 44
        RST_W   = (LCD_WIDTH - 24) // 2
        BCK_X   = 12 + RST_W + 4
        BCK_W   = LCD_WIDTH - BCK_X - 8

        def _draw():
            img = new_screen()
            draw_header(img, "Einstellungen")
            d = ImageDraw.Draw(img)

            for i, (attr, label, mn, mx, step, fmt) in enumerate(ROWS_NUM):
                y = y0 + i * ROW_STP
                d.text((8, y + 5), label, font=FONT_SMALL, fill=C_MUTED)
                draw_rounded_rect(d, BTN1_X, y, BTN_W, ROW_H, 5, C_SURFACE)
                bb = d.textbbox((0, 0), "-", font=FONT_MEDIUM)
                d.text((BTN1_X + (BTN_W - (bb[2]-bb[0])) // 2,
                        y + (ROW_H - (bb[3]-bb[1])) // 2),
                       "-", font=FONT_MEDIUM, fill=C_WHITE)
                val_str = fmt.format(getattr(self, attr))
                bb2 = d.textbbox((0, 0), val_str, font=FONT_SMALL)
                d.text((VAL_X + (VAL_W - (bb2[2]-bb2[0])) // 2, y + 5),
                       val_str, font=FONT_SMALL, fill=C_PRIMARY)
                draw_rounded_rect(d, BTN2_X, y, BTN_W, ROW_H, 5, C_SURFACE)
                bb3 = d.textbbox((0, 0), "+", font=FONT_MEDIUM)
                d.text((BTN2_X + (BTN_W - (bb3[2]-bb3[0])) // 2,
                        y + (ROW_H - (bb3[3]-bb3[1])) // 2),
                       "+", font=FONT_MEDIUM, fill=C_WHITE)

            for i, (attr, label) in enumerate(ROWS_BOOL):
                y   = y0 + (n_num + i) * ROW_STP
                val = getattr(self, attr)
                d.text((8, y + 5), label, font=FONT_SMALL, fill=C_MUTED)
                draw_rounded_rect(d, BTN1_X, y, BOOL_W, ROW_H, 5,
                                  C_SUCCESS if val else C_SURFACE)
                txt = "Ein" if val else "Aus"
                bb  = d.textbbox((0, 0), txt, font=FONT_SMALL)
                d.text((BTN1_X + (BOOL_W - (bb[2]-bb[0])) // 2, y + 5),
                       txt, font=FONT_SMALL, fill=C_WHITE)

            fi = filt_values.index(self.filter_mode) if self.filter_mode in filt_values else 0
            y  = y0 + (n_num + n_bool) * ROW_STP
            d.text((8, y + 5), "Filter", font=FONT_SMALL, fill=C_MUTED)
            for fx, lbl in [(FX1, "<"), (FX2, ">")]:
                draw_rounded_rect(d, fx, y, FBW, ROW_H, 5, C_SURFACE)
                bb = d.textbbox((0, 0), lbl, font=FONT_MEDIUM)
                d.text((fx + (FBW - (bb[2]-bb[0])) // 2,
                        y + (ROW_H - (bb[3]-bb[1])) // 2),
                       lbl, font=FONT_MEDIUM, fill=C_WHITE)
            draw_rounded_rect(d, FVX, y, FVW, ROW_H, 5, C_SURFACE)
            bb2 = d.textbbox((0, 0), filt_names[fi], font=FONT_SMALL)
            d.text((FVX + (FVW - (bb2[2]-bb2[0])) // 2, y + 5),
                   filt_names[fi], font=FONT_SMALL, fill=C_PRIMARY)

            draw_rounded_rect(d, 8, BOT_Y, RST_W, 36, 8, C_DANGER)
            bb = d.textbbox((0, 0), "Reset", font=FONT_MEDIUM)
            d.text((8 + (RST_W - (bb[2]-bb[0])) // 2,
                    BOT_Y + (36 - (bb[3]-bb[1])) // 2),
                   "Reset", font=FONT_MEDIUM, fill=C_WHITE)
            draw_rounded_rect(d, BCK_X, BOT_Y, BCK_W, 36, 8, C_MUTED)
            bb2 = d.textbbox((0, 0), "Zurueck", font=FONT_MEDIUM)
            d.text((BCK_X + (BCK_W - (bb2[2]-bb2[0])) // 2,
                    BOT_Y + (36 - (bb2[3]-bb2[1])) // 2),
                   "Zurueck", font=FONT_MEDIUM, fill=C_WHITE)
            self.lcd.show_image(img)

        _draw()

        while True:
            xy = self._get_touch()
            if not xy:
                time.sleep(TOUCH_TIMEOUT)
                continue
            tx, ty = xy
            changed = False

            for i, (attr, label, mn, mx, step, fmt) in enumerate(ROWS_NUM):
                y = y0 + i * ROW_STP
                if y <= ty <= y + ROW_H:
                    val = getattr(self, attr)
                    if BTN1_X <= tx <= BTN1_X + BTN_W:
                        setattr(self, attr, max(mn, round(val - step, 4)))
                        changed = True
                    elif BTN2_X <= tx <= BTN2_X + BTN_W:
                        setattr(self, attr, min(mx, round(val + step, 4)))
                        changed = True

            for i, (attr, label) in enumerate(ROWS_BOOL):
                y = y0 + (n_num + i) * ROW_STP
                if y <= ty <= y + ROW_H and tx >= BTN1_X:
                    setattr(self, attr, not getattr(self, attr))
                    changed = True

            fi = filt_values.index(self.filter_mode) if self.filter_mode in filt_values else 0
            y  = y0 + (n_num + n_bool) * ROW_STP
            if y <= ty <= y + ROW_H:
                if FX1 <= tx <= FX1 + FBW:
                    self.filter_mode = filt_values[(fi - 1) % len(filt_values)]
                    changed = True
                elif FX2 <= tx <= FX2 + FBW:
                    self.filter_mode = filt_values[(fi + 1) % len(filt_values)]
                    changed = True

            if BOT_Y <= ty:
                if tx <= 8 + RST_W:
                    self.zoom = 1.0; self.center_x = 0.0; self.center_y = 0.0
                    self.brightness = 0; self.contrast = 1.0; self.saturation = 1.0
                    self.mirror = False; self.freeze = False; self.filter_mode = "normal"
                    changed = True
                elif tx >= BCK_X:
                    self.save_settings()
                    self.show_main_menu()
                    return

            if changed:
                self.save_settings()
                _draw()

    # --------------------------------------------------
    # Hauptschleife
    # --------------------------------------------------
    def run(self):
        try:
            while True:
                self.show_main_menu()
        except KeyboardInterrupt:
            print("\nBeendet.")
        finally:
            self.lcd.clear()


# ========================================
# Einstiegspunkt
# ========================================

if __name__ == "__main__":
    app = SmartBinApp()
    app.run()

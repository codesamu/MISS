#!/usr/bin/env python3
"""Automatische Fotoaufnahme mit Livebild auf dem SmartBin-Display."""

from __future__ import annotations

import argparse
import io
import queue
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


APP_DIR = Path(__file__).resolve().parent
DRIVER_DIR = APP_DIR.parent / "display-cam-gui"
DEFAULT_OUTPUT_DIR = APP_DIR / "photos"

LCD_WIDTH = 480
LCD_HEIGHT = 320
PREVIEW_HEIGHT = 270

# Der 4:3-Modus 1296x972 der OV5647 liest laut rpicam den kompletten
# 2592x1944-Sensorbereich aus. 1920x1080 wuerde das Bild oben, unten und an den
# Seiten beschneiden und damit nicht das volle Sichtfeld aufnehmen.
CAMERA_WIDTH = 1296
CAMERA_HEIGHT = 972
CAMERA_SENSOR_MODE = "1296:972:10"
CAMERA_FRAMERATE = 10

FONT_REGULAR_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

C_PANEL = (24, 27, 34)
C_WHITE = (255, 255, 255)
C_MUTED = (174, 181, 195)
C_RED = (213, 48, 48)
C_GREEN = (43, 190, 102)
C_BLACK = (0, 0, 0)


@dataclass(frozen=True)
class CameraFrame:
    image: Image.Image
    jpeg: bytes


class TouchButton:
    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def contains(self, x: int, y: int) -> bool:
        return (
            self.x <= x <= self.x + self.width
            and self.y <= y <= self.y + self.height
        )


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


FONT_SMALL = load_font(FONT_REGULAR_PATH, 13)
FONT_MEDIUM = load_font(FONT_BOLD_PATH, 18)


def fit_preview(image: Image.Image) -> Image.Image:
    """Passt das komplette Bild ohne Beschnitt in die 480x270-Vorschau ein."""
    source = image.convert("RGB")
    scale = min(LCD_WIDTH / source.width, PREVIEW_HEIGHT / source.height)
    width = max(1, round(source.width * scale))
    height = max(1, round(source.height * scale))
    resized = source.resize((width, height), Image.Resampling.BILINEAR)

    preview = Image.new("RGB", (LCD_WIDTH, PREVIEW_HEIGHT), C_BLACK)
    preview.paste(
        resized,
        ((LCD_WIDTH - width) // 2, (PREVIEW_HEIGHT - height) // 2),
    )
    return preview


def next_photo_path(output_dir: Path, captured_at: datetime) -> Path:
    """Erzeugt einen eindeutigen, chronologisch sortierbaren Dateinamen."""
    base = captured_at.strftime("muell_%Y%m%d_%H%M%S_%f")[:-3]
    candidate = output_dir / f"{base}.jpg"
    suffix = 1
    while candidate.exists():
        candidate = output_dir / f"{base}_{suffix}.jpg"
        suffix += 1
    return candidate


class MjpegCamera:
    """Liest einzelne JPEG-Frames aus einem rpicam-vid-MJPEG-Stream."""

    def __init__(
        self,
        width: int,
        height: int,
        framerate: int,
        sensor_mode: str,
    ) -> None:
        self.width = width
        self.height = height
        self.framerate = framerate
        self.sensor_mode = sensor_mode
        self.frames: queue.Queue[CameraFrame] = queue.Queue(maxsize=2)
        self.process: subprocess.Popen[bytes] | None = None
        self.reader_thread: threading.Thread | None = None
        self.stop_event = threading.Event()

    def start(self) -> None:
        executable = shutil.which("rpicam-vid")
        if executable is None:
            raise RuntimeError("rpicam-vid wurde nicht gefunden.")

        command = [
            executable,
            "--timeout", "0",
            "--codec", "mjpeg",
            "--output", "-",
            "--width", str(self.width),
            "--height", str(self.height),
            "--framerate", str(self.framerate),
            "--mode", self.sensor_mode,
            "--nopreview",
        ]
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.reader_thread = threading.Thread(
            target=self._read_frames,
            name="camera-reader",
            daemon=True,
        )
        self.reader_thread.start()

    def _publish(self, jpeg: bytes) -> None:
        try:
            image = Image.open(io.BytesIO(jpeg))
            image.load()
            frame = CameraFrame(image=image, jpeg=jpeg)
        except Exception:
            return

        if self.frames.full():
            try:
                self.frames.get_nowait()
            except queue.Empty:
                pass
        try:
            self.frames.put_nowait(frame)
        except queue.Full:
            pass

    def _read_frames(self) -> None:
        if self.process is None or self.process.stdout is None:
            return

        buffer = bytearray()
        while not self.stop_event.is_set():
            chunk = self.process.stdout.read(65536)
            if not chunk:
                break
            buffer.extend(chunk)

            while True:
                start = buffer.find(b"\xff\xd8")
                if start < 0:
                    if len(buffer) > 1:
                        del buffer[:-1]
                    break

                end = buffer.find(b"\xff\xd9", start + 2)
                if end < 0:
                    if start > 0:
                        del buffer[:start]
                    break

                jpeg = bytes(buffer[start:end + 2])
                del buffer[:end + 2]
                self._publish(jpeg)

    def latest(self, timeout: float) -> CameraFrame | None:
        try:
            frame = self.frames.get(timeout=timeout)
        except queue.Empty:
            return None

        while True:
            try:
                frame = self.frames.get_nowait()
            except queue.Empty:
                return frame

    def failed(self) -> bool:
        return self.process is not None and self.process.poll() is not None

    def close(self) -> None:
        self.stop_event.set()
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        if self.reader_thread is not None:
            self.reader_thread.join(timeout=1)


class PhotoCollectorApp:
    def __init__(
        self,
        output_dir: Path,
        interval: float,
    ) -> None:
        if not DRIVER_DIR.is_dir():
            raise RuntimeError(f"Hardwaretreiber fehlen: {DRIVER_DIR}")
        sys.path.insert(0, str(DRIVER_DIR))

        try:
            import ft6336u  # type: ignore[import-not-found]
            import st7796  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(f"Hardwaretreiber konnten nicht geladen werden: {exc}") from exc

        self.output_dir = output_dir.resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.interval = interval
        self.camera = MjpegCamera(
            CAMERA_WIDTH,
            CAMERA_HEIGHT,
            CAMERA_FRAMERATE,
            CAMERA_SENSOR_MODE,
        )
        self.stop_button = TouchButton(350, PREVIEW_HEIGHT + 5, 122, 40)
        self.photo_count = 0
        self.running = True
        self.lcd = None
        self.touch = None

        try:
            self.lcd = st7796.st7796()
            self.touch = ft6336u.ft6336u()
        except Exception as exc:
            self.close_hardware()
            raise RuntimeError(f"Display/Touch konnte nicht gestartet werden: {exc}") from exc

    def get_touch(self) -> tuple[int, int] | None:
        if self.touch is None:
            return None
        self.touch.read_touch_data()
        result = self.touch.get_touch_xy()
        if not result:
            return None
        point_count, coordinates = result
        if point_count == 0 or not coordinates:
            return None

        portrait_x = coordinates[0]["x"]
        portrait_y = coordinates[0]["y"]
        return 479 - portrait_y, 319 - portrait_x

    def draw_screen(self, frame: CameraFrame, seconds_left: float) -> None:
        screen = Image.new("RGB", (LCD_WIDTH, LCD_HEIGHT), C_BLACK)
        screen.paste(fit_preview(frame.image), (0, 0))

        draw = ImageDraw.Draw(screen)
        draw.rectangle(
            (0, PREVIEW_HEIGHT, LCD_WIDTH, LCD_HEIGHT),
            fill=C_PANEL,
        )
        draw.ellipse((10, 286, 20, 296), fill=C_GREEN)
        draw.text(
            (27, 274),
            f"{self.photo_count} Fotos",
            font=FONT_MEDIUM,
            fill=C_WHITE,
        )
        draw.text(
            (27, 299),
            f"Naechstes in {max(0.0, seconds_left):.1f} s",
            font=FONT_SMALL,
            fill=C_MUTED,
        )

        x = self.stop_button.x
        y = self.stop_button.y
        w = self.stop_button.width
        h = self.stop_button.height
        draw.rounded_rectangle((x, y, x + w, y + h), radius=9, fill=C_RED)
        text_box = draw.textbbox((0, 0), "STOP", font=FONT_MEDIUM)
        text_width = text_box[2] - text_box[0]
        text_height = text_box[3] - text_box[1]
        draw.text(
            (x + (w - text_width) // 2, y + (h - text_height) // 2 - 1),
            "STOP",
            font=FONT_MEDIUM,
            fill=C_WHITE,
        )
        self.lcd.show_image(screen)

    def show_message(self, title: str, detail: str, color: tuple[int, int, int]) -> None:
        if self.lcd is None:
            return
        screen = Image.new("RGB", (LCD_WIDTH, LCD_HEIGHT), C_PANEL)
        draw = ImageDraw.Draw(screen)
        title_box = draw.textbbox((0, 0), title, font=FONT_MEDIUM)
        draw.text(
            ((LCD_WIDTH - (title_box[2] - title_box[0])) // 2, 120),
            title,
            font=FONT_MEDIUM,
            fill=color,
        )
        detail_box = draw.textbbox((0, 0), detail, font=FONT_SMALL)
        draw.text(
            ((LCD_WIDTH - (detail_box[2] - detail_box[0])) // 2, 158),
            detail,
            font=FONT_SMALL,
            fill=C_WHITE,
        )
        self.lcd.show_image(screen)

    def save_photo(self, frame: CameraFrame) -> None:
        destination = next_photo_path(self.output_dir, datetime.now())
        destination.write_bytes(frame.jpeg)
        self.photo_count += 1
        print(f"Gespeichert: {destination}", flush=True)

    def run(self) -> None:
        self.show_message("Kamera startet ...", "Bitte kurz warten", C_WHITE)
        self.camera.start()

        current_frame: CameraFrame | None = None
        first_frame_deadline = time.monotonic() + 15
        next_capture: float | None = None
        last_frame_at: float | None = None

        while self.running:
            frame = self.camera.latest(timeout=0.08)
            if frame is not None:
                current_frame = frame
                last_frame_at = time.monotonic()
                if next_capture is None:
                    next_capture = last_frame_at + self.interval

            now = time.monotonic()
            if current_frame is None:
                if self.camera.failed() or now >= first_frame_deadline:
                    raise RuntimeError("Kein Kamerabild empfangen.")
                continue
            if self.camera.failed() or (
                last_frame_at is not None and now - last_frame_at > 5
            ):
                raise RuntimeError("Die Kamera liefert keine neuen Bilder.")

            if next_capture is not None and now >= next_capture:
                self.save_photo(current_frame)
                while next_capture <= now:
                    next_capture += self.interval

            seconds_left = (next_capture - now) if next_capture is not None else self.interval
            self.draw_screen(current_frame, seconds_left)

            touched = self.get_touch()
            if touched is not None and self.stop_button.contains(*touched):
                self.running = False

        self.show_message(
            "Aufnahme beendet",
            f"{self.photo_count} Fotos gespeichert",
            C_GREEN,
        )
        time.sleep(1.5)

    def close_hardware(self) -> None:
        if self.lcd is not None:
            try:
                self.lcd.clear()
            except Exception:
                pass
            try:
                self.lcd.close()
            except Exception:
                pass
            self.lcd = None
        if self.touch is not None:
            try:
                self.touch.close()
            except Exception:
                pass
            self.touch = None

    def close(self) -> None:
        self.camera.close()
        self.close_hardware()


def positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Der Wert muss groesser als 0 sein.")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Zeigt die Kamera an und speichert automatisch Fotos.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Zielordner fuer Fotos (Standard: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--interval",
        type=positive_float,
        default=5.0,
        help="Sekunden zwischen Fotos (Standard: 5)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app: PhotoCollectorApp | None = None
    try:
        app = PhotoCollectorApp(
            output_dir=args.output_dir,
            interval=args.interval,
        )
        print(f"Fotos werden in {app.output_dir} gespeichert.")
        app.run()
        return 0
    except KeyboardInterrupt:
        print("\nAufnahme abgebrochen.")
        return 0
    except Exception as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        if app is not None:
            try:
                app.show_message("Fehler", str(exc)[:55], C_RED)
                time.sleep(4)
            except Exception:
                pass
        return 1
    finally:
        if app is not None:
            app.close()


if __name__ == "__main__":
    raise SystemExit(main())

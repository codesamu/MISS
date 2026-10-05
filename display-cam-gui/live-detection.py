#!/usr/bin/env python3
"""Trainierte YOLO-Modelle auf dem Kamerastream ausfuehren und am LCD anzeigen."""

import argparse
import importlib.util
import sys
import time
from contextlib import ExitStack
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
WIDTH, HEIGHT = 480, 320
BAR_HEIGHT = 36
COLORS = ("#30ee80", "#ffcc33", "#44bbff", "#ff88dd")
DEFAULT_ENTER_CONFIDENCE = 0.60
DEFAULT_KEEP_CONFIDENCE = 0.60
DEFAULT_CONFIRM_FRAMES = 2
DEFAULT_RELEASE_FRAMES = 4
CAMERA_START_TIMEOUT = 15
CAMERA_STALL_TIMEOUT = 10


def find_models():
    """Find detection weights only, newest first."""
    paths = set()
    exported = ROOT / "YOLO" / "pet.pt"
    if exported.is_file():
        paths.add(exported)
    for directory in (ROOT / "YOLO" / "runs", ROOT / "runs" / "detect"):
        if directory.is_dir():
            paths.update(directory.glob("**/weights/best.pt"))

    def is_detector(path):
        if path == exported:
            return True
        args_file = path.parent.parent / "args.yaml"
        if not args_file.is_file():
            return True  # The model task is checked again after loading.
        return "task: detect" in args_file.read_text(encoding="utf-8")

    return sorted(
        (path for path in paths if is_detector(path)),
        key=lambda path: (path.stat().st_mtime_ns, str(path)),
        reverse=True,
    )


def camera_class():
    # Den vorhandenen MJPEG-Leser wiederverwenden, ohne die Foto-App zu starten.
    spec = importlib.util.spec_from_file_location(
        "smartbin_capture", ROOT / "capture-photos" / "main.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.MjpegCamera


def load_font(size=15):
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size
        )
    except OSError:
        return ImageFont.load_default()


def label(draw, xy, text, color, font):
    x, y = xy
    bounds = draw.textbbox((x, y), text, font=font)
    draw.rectangle((x, y, bounds[2] + 4, bounds[3] + 3), fill="black")
    draw.text((x + 2, y), text, fill=color, font=font)


class DetectionStabilizer:
    """Debounce noisy frame-wise detections using confidence hysteresis."""

    def __init__(self, enter_confidence, keep_confidence, confirm_frames, release_frames):
        if not 0 <= keep_confidence <= enter_confidence <= 1:
            raise ValueError("Confidence muss 0 <= keep <= enter <= 1 erfuellen.")
        if confirm_frames < 1 or release_frames < 1:
            raise ValueError("Frame-Anzahlen muessen mindestens 1 sein.")
        self.enter_confidence = enter_confidence
        self.keep_confidence = keep_confidence
        self.confirm_frames = confirm_frames
        self.release_frames = release_frames
        self.detected = False
        self._hits = 0
        self._misses = 0

    def update(self, confidence):
        threshold = self.keep_confidence if self.detected else self.enter_confidence
        hit = confidence > 0 and confidence >= threshold
        if self.detected:
            self._misses = 0 if hit else self._misses + 1
            if self._misses >= self.release_frames:
                self.detected = False
                self._misses = 0
                self._hits = 0
        else:
            self._hits = self._hits + 1 if hit else 0
            if self._hits >= self.confirm_frames:
                self.detected = True
                self._hits = 0
                self._misses = 0
        return self.detected


class MultiClassStabilizer:
    """Jede Klasse unabhaengig bestaetigen und wieder freigeben."""

    def __init__(self, *settings):
        self.settings = settings
        self.states = {}

    def update(self, results):
        scores = {}
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    name = result.names[int(box.cls.item())].strip()
                    scores[name] = max(scores.get(name, 0.0), float(box.conf.item()))
        for name in scores:
            if name not in self.states:
                self.states[name] = DetectionStabilizer(*self.settings)
        return {
            name: scores.get(name, 0.0)
            for name, state in self.states.items()
            if state.update(scores.get(name, 0.0))
        }


def fit_text(draw, text, font, width):
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "...", font=font) > width:
        text = text[:-1]
    return text + "..."


def draw_status(draw, active, font):
    lines = [f"{name} erkannt" + (f" | {score:.0%}" if score > 0 else "")
             for name, score in sorted(active.items())]
    if len(lines) > 4:
        lines = lines[:3] + [f"+ {len(lines) - 3} weitere Klassen erkannt"]
    for index, text in enumerate(lines or ["Kein Objekt erkannt"]):
        text = fit_text(draw, text, font, WIDTH - 36)
        y = 5 + index * 28
        width = draw.textlength(text, font=font) + 18
        fill = "#168a4c" if active else "#343943"
        draw.rounded_rectangle((6, y, 6 + width, y + 26), radius=6, fill=fill)
        draw.text((15, y + 4), text, fill="white", font=font)


def render(frame, results, box_confidence, active, fps, font):
    """Boxen zum selben Kamerabild zeichnen, einschliesslich Letterbox-Versatz."""
    screen = Image.new("RGB", (WIDTH, HEIGHT), "black")
    preview = ImageOps.contain(frame, (WIDTH, HEIGHT - BAR_HEIGHT))
    ox = (WIDTH - preview.width) // 2
    oy = (HEIGHT - BAR_HEIGHT - preview.height) // 2
    screen.paste(preview, (ox, oy))
    draw = ImageDraw.Draw(screen)
    sx, sy = preview.width / frame.width, preview.height / frame.height
    names = sorted({name.strip() for result in results for name in (
        result.names.values() if isinstance(result.names, dict) else result.names
    )})
    colors = {name: COLORS[index % len(COLORS)] for index, name in enumerate(names)}
    for result in results:
        if result.boxes is not None:
            for box in result.boxes:
                score = float(box.conf.item())
                if score < box_confidence:
                    continue
                name = result.names[int(box.cls.item())].strip()
                color = colors[name]
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                coords = (ox + x1 * sx, oy + y1 * sy,
                          ox + x2 * sx, oy + y2 * sy)
                draw.rectangle(coords, outline=color, width=2)
                label(draw, (coords[0], max(0, coords[1] - 20)),
                      f"{name} {score:.0%}", color, font)
    draw_status(draw, active, font)
    draw.rectangle((0, HEIGHT - BAR_HEIGHT, WIDTH, HEIGHT), fill="#181b22")
    draw.text((8, HEIGHT - BAR_HEIGHT + 8), f"Live | KI: {fps:.1f} FPS", font=font, fill="white")
    draw.rectangle((WIDTH - 100, HEIGHT - BAR_HEIGHT, WIDTH, HEIGHT), fill="#b52c32")
    draw.text((WIDTH - 86, HEIGHT - BAR_HEIGHT + 8), "Beenden", font=font, fill="white")
    return screen


def touch_position(touch):
    touch.read_touch_data()
    point, coords = touch.get_touch_xy() or (0, [])
    if not point or not coords:
        return None
    return 479 - coords[0]["y"], 319 - coords[0]["x"]


def stop_touched(touch):
    position = touch_position(touch)
    return position is not None and (
        WIDTH - 100 <= position[0] < WIDTH and HEIGHT - BAR_HEIGHT <= position[1] < HEIGHT
    )


def model_title(path):
    if path.parent.name == "weights":
        run = path.parent.parent
        if run.name == "train" and run.parent.name not in ("detect", "runs"):
            run = run.parent
        return f"{run.name} / {path.name}"
    return f"{path.name} (Modellkopie)"


def choose_model(lcd, touch, paths, font):
    """Vier Modelle pro Seite; erst ein neuer Fingerdruck waehlt aus."""
    page = 0
    pages = (len(paths) + 3) // 4
    pressed = True  # Den Start-Tipp aus dem Dashboard nicht uebernehmen.
    redraw = True
    while True:
        if redraw:
            screen = Image.new("RGB", (WIDTH, HEIGHT), "#181b22")
            draw = ImageDraw.Draw(screen)
            draw.text((12, 12), f"Modell waehlen ({page + 1}/{pages})", font=font, fill="white")
            for row, path in enumerate(paths[page * 4:page * 4 + 4]):
                y = 48 + row * 55
                draw.rounded_rectangle((8, y, WIDTH - 8, y + 48), radius=5, fill="#343943")
                text = fit_text(draw, model_title(path), font, WIDTH - 36)
                draw.text((18, y + 14), text, font=font, fill="white")
            for x, text in ((12, "Zurueck"), (175, "Weiter"), (365, "Abbrechen")):
                draw.text((x, 290), text, font=font, fill="white")
            lcd.show_image(screen)
            redraw = False
        position = touch_position(touch)
        if position is not None and not pressed:
            x, y = position
            if 8 <= x < WIDTH - 8 and 48 <= y < 268:
                row, offset = divmod(y - 48, 55)
                index = page * 4 + row
                if offset < 48 and index < len(paths):
                    return paths[index]
            elif HEIGHT - BAR_HEIGHT <= y < HEIGHT:
                if x >= 350:
                    return None
                if x < 160:
                    page = max(0, page - 1)
                else:
                    page = min(pages - 1, page + 1)
                redraw = True
        pressed = position is not None
        time.sleep(0.03)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, nargs="+", help="Eine oder mehrere trainierte .pt-Dateien")
    parser.add_argument("--list-models", action="store_true", help="Verfuegbare Modelle anzeigen")
    parser.add_argument(
        "--conf", type=float, default=DEFAULT_ENTER_CONFIDENCE,
        help="Schwelle zum Einschalten der Erkennung (Standard: 0.60)",
    )
    parser.add_argument(
        "--keep-conf", type=float, default=DEFAULT_KEEP_CONFIDENCE,
        help="Halteschwelle gegen Flackern (Standard: 0.60)",
    )
    parser.add_argument(
        "--confirm-frames", type=int, default=DEFAULT_CONFIRM_FRAMES,
        help="Treffer in Folge bis 'erkannt' (Standard: 2)",
    )
    parser.add_argument(
        "--release-frames", type=int, default=DEFAULT_RELEASE_FRAMES,
        help="Fehlende Treffer in Folge bis 'nicht erkannt' (Standard: 4)",
    )
    parser.add_argument("--imgsz", type=int, default=640, help="Inferenzgroesse (Standard: 640)")
    parser.add_argument("--max-frames", type=int, default=0, help="Nach N Bildern beenden; 0 = unbegrenzt")
    args = parser.parse_args()
    if not 0 <= args.conf <= 1:
        parser.error("--conf muss zwischen 0 und 1 liegen.")
    if not 0 <= args.keep_conf <= args.conf:
        parser.error("--keep-conf muss zwischen 0 und --conf liegen.")
    if args.confirm_frames < 1 or args.release_frames < 1:
        parser.error("--confirm-frames und --release-frames muessen mindestens 1 sein.")
    if args.imgsz <= 0:
        parser.error("--imgsz muss positiv sein.")
    if args.max_frames < 0:
        parser.error("--max-frames darf nicht negativ sein.")
    return args


def main():
    args = parse_args()
    available = find_models()
    if args.list_models:
        for path in available:
            print(path.relative_to(ROOT))
        return 0
    paths = args.model or available
    if not paths:
        raise RuntimeError(
            "Kein trainiertes Detection-Modell gefunden. Zuerst 'python YOLO/train.py' "
            "ausfuehren oder mit --model den Pfad zu einem Detection-best.pt angeben. "
            "Die vorhandenen runs/classify-Modelle koennen keine Bounding Boxes liefern."
        )
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Modell nicht gefunden: {path}")

    from ultralytics import YOLO
    import torch
    import st7796
    import ft6336u

    torch.set_num_threads(4)
    font = load_font()
    state = MultiClassStabilizer(
        args.conf, args.keep_conf, args.confirm_frames, args.release_frames
    )
    with ExitStack() as resources:
        touch = ft6336u.ft6336u()
        resources.callback(touch.close)
        lcd = st7796.st7796()
        # PWM stoppen, bevor der Touch-Treiber die gemeinsam genutzten GPIOs freigibt.
        resources.callback(lcd.close)
        if not args.model:
            selected = choose_model(lcd, touch, available, font)
            if selected is None:
                return 0
            paths = [selected]
        loading = Image.new("RGB", (WIDTH, HEIGHT), "black")
        ImageDraw.Draw(loading).text((20, 140), "Modell wird geladen ...", font=font, fill="white")
        lcd.show_image(loading)
        models = []
        for path in paths:
            model = YOLO(str(path.resolve()))
            if model.task != "detect":
                raise RuntimeError(
                    f"{path}: Aufgabe ist '{model.task}', benoetigt wird 'detect'. "
                    "Ein Klassifikationsmodell kann keine Bounding Boxes liefern."
                )
            print(f"Modell: {path} | Klassen: {model.names}", flush=True)
            models.append(model)

        # Die angeschlossene OV5647 liefert mit 10 FPS keine Frames; 30 FPS sind getestet.
        camera = camera_class()(width=640, height=480, framerate=30, sensor_mode="1296:972:10")
        resources.callback(camera.close)
        loading = Image.new("RGB", (WIDTH, HEIGHT), "black")
        ImageDraw.Draw(loading).text((20, 140), "Kamera startet ...", font=font, fill="white")
        lcd.show_image(loading)
        camera.start()
        last_frame = time.monotonic()
        first_frame_received = False
        count = 0
        while not stop_touched(touch):
            frame = camera.latest(timeout=0.1)
            if frame is None:
                if camera.failed():
                    reason = camera.failure_reason()
                    detail = f" Ursache: {reason}" if reason else ""
                    raise RuntimeError(f"Kameraprozess wurde beendet.{detail}")
                timeout = CAMERA_STALL_TIMEOUT if first_frame_received else CAMERA_START_TIMEOUT
                if time.monotonic() - last_frame > timeout:
                    phase = "abgebrochen" if first_frame_received else "nicht gestartet"
                    raise RuntimeError(
                        f"Kamerastream ist {phase}: {timeout} Sekunden ohne Bild. "
                        "Andere Kamera-Apps beenden und erneut versuchen."
                    )
                continue
            first_frame_received = True
            start = time.monotonic()
            source = frame.image.convert("RGB")
            results = [
                model.predict(source, conf=args.keep_conf,
                              imgsz=args.imgsz,
                              device="cpu", verbose=False, save=False)[0]
                for model in models
            ]
            active = state.update(results)
            fps = 1 / max(time.monotonic() - start, 0.001)
            lcd.show_image(
                render(
                    source, results, args.keep_conf, active, fps, font
                )
            )
            last_frame = time.monotonic()
            count += 1
            if args.max_frames and count >= args.max_frames:
                break
        print(f"Live-Erkennung beendet ({count} Bilder).", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nLive-Erkennung beendet.")
    except Exception as error:
        print(f"Fehler: {error}", file=sys.stderr)
        sys.exit(1)

"""Raspberry Pi bindings; imported only for the real hardware start."""

from contextlib import ExitStack, contextmanager
import importlib.util
from pathlib import Path
import sys
import threading
import time

from .app import EventLog, run
from .config import PROJECT
from .display import DamageDisplay, LatestDisplay
from .servos import TimedSorter
from .view import loading
from .vision import BackgroundVision


@contextmanager
def loading_animation(display):
    stop = threading.Event()

    def animate():
        while not stop.is_set():
            try:
                display.show_image(loading(time.monotonic()))
            except RuntimeError:
                return
            stop.wait(1 / 30)

    thread = threading.Thread(target=animate, name="miss-startup", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=1)


def load_camera_class():
    path = PROJECT / "capture-photos" / "main.py"
    spec = importlib.util.spec_from_file_location("miss_camera_source", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.MjpegCamera


def run_hardware(config, log_path=None):
    if not config.model_path.is_file():
        raise FileNotFoundError(f"YOLO-Modell fehlt: {config.model_path}")
    driver_dir = PROJECT / "display-cam-gui"
    sys.path.insert(0, str(driver_dir))
    import ft6336u
    import st7796
    from gpiozero import Servo

    with ExitStack() as resources:
        touch = ft6336u.ft6336u()
        resources.callback(touch.close)
        lcd = LatestDisplay(DamageDisplay(st7796.st7796()))
        resources.callback(lcd.close)
        lcd.show_image(loading())
        with loading_animation(lcd):
            from ultralytics import YOLO
            import torch

            torch.set_num_threads(4)
            detector = YOLO(str(config.model_path))
            if detector.task != "detect":
                raise ValueError("MISS benötigt ein YOLO-Detection-Modell.")
            names = detector.names.values() if isinstance(detector.names, dict) else detector.names
            if not set(config.routes).intersection(name.strip() for name in names):
                raise ValueError("Keine Modellklasse hat eine Sortierzuordnung in config.json.")
        horizontal = Servo(16)
        resources.callback(horizontal.close)
        vertical = Servo(20)
        resources.callback(vertical.close)
        sorter = TimedSorter(horizontal, vertical, config)
        resources.callback(sorter.close)
        camera = load_camera_class()(640, 480, 30, "1296:972:10")
        vision = BackgroundVision(camera, detector, config)
        resources.callback(vision.close)
        log = EventLog(log_path or Path(__file__).parent / "data" / "feedback.jsonl")
        run(lcd, touch, vision, sorter, config, log)

"""Hardware doubles used only by the desktop simulation process."""

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
import io
from pathlib import Path
import sys
import threading
import time
from types import ModuleType, SimpleNamespace

from PIL import Image, ImageDraw, ImageFont, ImageOps


SIZE = (480, 320)
SCENES = ("Plastikflasche", "Aludose", "Beide", "Kein Objekt", "Am Plattenrand", "Außerhalb der Platte")


class SimulationClosed(BaseException):
    pass


class ReturnToDashboard(BaseException):
    pass


def portrait_touch(x, y):
    """Inverse of the existing apps' landscape coordinate transformation."""
    return {"x": 319 - y, "y": 479 - x}


class Surface:
    """In-memory display, also usable without Tk for integration checks."""

    def __init__(self):
        self.frame = Image.new("RGB", SIZE, "black")
        self.clicks = deque()
        self.scene = SCENES[0]
        self.confidence = 0.85
        self.custom_image = None
        self.servos = {}
        self.events = deque(maxlen=30)
        self.active_app = "dashboard"
        self.home_requested = False
        self.closed = False
        self.remove_after_sort = True
        self.plate = (0.18, 0.16, 0.82, 0.88)
        self.workflow_state = None
        self.workflow_since = 0
        self.pointer = None

    def pump(self):
        if self.closed:
            raise SimulationClosed()
        if self.home_requested and self.active_app != "dashboard":
            self.home_requested = False
            raise ReturnToDashboard()

    def show(self, frame):
        self.frame = frame.convert("RGB").copy()
        self.pump()

    def sleep(self, seconds):
        # Python 3.12's Windows monotonic clock can have ~15 ms resolution.
        # perf_counter keeps a 60 Hz preview from accidentally waiting 31 ms.
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            self.pump()
            time.sleep(min(0.008, max(0, deadline - time.perf_counter())))

    def log(self, message):
        self.events.append(message)

    def sort_completed(self):
        self.log("Sortierung abgeschlossen")
        if self.remove_after_sort:
            self.scene = "Kein Objekt"

    def camera_image(self, size):
        if self.custom_image is not None:
            return ImageOps.fit(self.custom_image, size)
        image = Image.new("RGB", (640, 480), "#303b43")
        draw = ImageDraw.Draw(image)
        for x in range(0, 640, 40):
            draw.line((x, 0, x, 480), fill="#394650")
        for y in range(0, 480, 40):
            draw.line((0, y, 640, y), fill="#394650")
        plate = tuple(value * (640 if i % 2 == 0 else 480) for i, value in enumerate(self.plate))
        draw.rounded_rectangle(plate, radius=18, outline="#71828c", width=3)
        for class_id, box in self.objects():
            x1, y1, x2, y2 = box
            if class_id == 1:
                draw.rounded_rectangle(box, radius=25, fill="#5ca7bc", outline="#b1edf7", width=3)
                draw.rectangle((x1 + 21, y1 - 22, x2 - 21, y1 + 12), fill="#76ced8")
                draw.rectangle((x1 + 24, y1 - 32, x2 - 24, y1 - 22), fill="#2e8a92")
                draw.rectangle((x1 + 5, y1 + 85, x2 - 5, y2 - 70), fill="#dce9dd")
                draw.text((x1 + 25, y1 + 103), "PET", fill="#286d68")
            else:
                draw.rounded_rectangle(box, radius=16, fill="#b2bbc4", outline="#edf4fa", width=3)
                draw.ellipse((x1, y1, x2, y1 + 22), fill="#e0e5e9", outline="#7d8b96", width=2)
                draw.rectangle((x1 + 3, y1 + 45, x2 - 3, y2 - 28), fill="#d98040")
                draw.text((x1 + 21, y1 + 92), "ALU", fill="white")
        draw.text((18, 16), "MISS / SIMULIERTE KAMERA", fill="#d2dee6")
        return image.resize(size, Image.Resampling.BILINEAR)

    def objects(self):
        if self.custom_image is not None:
            return []  # Arbitrary images must not receive fabricated detections.
        objects = []
        if self.scene in ("Plastikflasche", "Beide"):
            objects.append((1, (190, 130, 280, 390)))
        if self.scene in ("Aludose", "Beide"):
            objects.append((0, (345, 175, 440, 375)))
        if self.scene == "Am Plattenrand":
            objects.append((1, (70, 130, 160, 390)))
        if self.scene == "Außerhalb der Platte":
            objects.append((1, (10, 130, 100, 390)))
        return objects


@dataclass
class CameraFrame:
    image: Image.Image
    jpeg: bytes


class Scalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class Coordinates:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


class Devices:
    def __init__(self, surface):
        self.surface = surface

    def lcd(self):
        surface = self.surface

        class Display:
            width, height = 320, 480

            @property
            def pointer(self):
                return surface.pointer

            def set_state(self, state, now):
                if state != surface.workflow_state:
                    surface.workflow_state = state
                    surface.workflow_since = now

            def show_image(self, image):
                if image.size != SIZE:
                    raise ValueError(f"Display erwartet {SIZE}, erhalten: {image.size}")
                surface.show(image)

            def clear(self):
                surface.frame = Image.new("RGB", SIZE, "white")

            def close(self):
                pass

        return Display()

    def touch(self):
        surface = self.surface

        class Touch:
            current = None

            def read_touch_data(self):
                surface.pump()
                self.current = surface.clicks.popleft() if surface.clicks else None

            def get_touch_xy(self):
                current, self.current = self.current, None
                return (1, [portrait_touch(*current)]) if current is not None else (0, [])

            def close(self):
                pass

        return Touch()

    def servo(self, pin, **kwargs):
        surface = self.surface

        class Servo:
            def __init__(self):
                self.value = None

            @property
            def value(self):
                return surface.servos.get(pin)

            @value.setter
            def value(self, value):
                surface.servos[pin] = value

            def move(self, value, name):
                self.value = value
                surface.log(f"GPIO {pin}: {name}")

            def min(self):
                self.move(-1, "Minimum")

            def mid(self):
                self.move(0, "Mitte")

            def max(self):
                self.move(1, "Maximum")

            def close(self):
                self.value = None

        return Servo()

    def camera(self, width, height, framerate, sensor_mode):
        surface = self.surface

        class Camera:
            def start(self):
                pass

            def latest(self, timeout=0.1):
                surface.sleep(min(timeout, 0.07))
                image = surface.camera_image((width, height))
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=85)
                return CameraFrame(image, buffer.getvalue())

            def failed(self):
                return False

            def failure_reason(self):
                return ""

            def close(self):
                pass

        return Camera()

    def camera_process(self, command, **kwargs):
        """MJPEG stdout substitute for the original manual camera app's reader."""
        surface = self.surface
        width = int(command[command.index("--width") + 1])
        height = int(command[command.index("--height") + 1])
        stopped = threading.Event()

        class Stream:
            def read(self, size):
                if stopped.wait(1 / 15):
                    return b""
                buffer = io.BytesIO()
                surface.camera_image((width, height)).save(buffer, format="JPEG", quality=85)
                return buffer.getvalue()

            def close(self):
                stopped.set()

        class Process:
            stdout = Stream()

            def terminate(self):
                stopped.set()

            kill = terminate

            def wait(self, timeout=None):
                stopped.set()
                return 0

        return Process()

    def yolo(self, path, latency=0.04):
        surface = self.surface

        class Detector:
            task = "detect"
            names = {0: "aluminum-can", 1: "plastic-bottle"}

            def predict(self, source, conf=0.6, **kwargs):
                if latency:
                    surface.sleep(latency)
                boxes = []
                for class_id, coords in surface.objects():
                    if surface.confidence >= conf:
                        scaled = [coords[i] * (source.width / 640 if i % 2 == 0 else source.height / 480)
                                  for i in range(4)]
                        boxes.append(SimpleNamespace(
                            cls=Scalar(class_id), conf=Scalar(surface.confidence),
                            xyxy=[Coordinates(scaled)],
                        ))
                return [SimpleNamespace(boxes=boxes, names=self.names)]

        return Detector()

    @contextmanager
    def installed(self):
        replacements = {
            "st7796": {"st7796": self.lcd},
            "ft6336u": {"ft6336u": self.touch},
            "gpiozero": {"Servo": self.servo},
            "ultralytics": {"YOLO": self.yolo},
            "torch": {"set_num_threads": lambda count: None},
        }
        previous = {name: sys.modules.get(name) for name in replacements}
        for name, attributes in replacements.items():
            module = ModuleType(name)
            module.__dict__.update(attributes)
            sys.modules[name] = module
        try:
            yield
        finally:
            for name, module in previous.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module


@contextmanager
def desktop_fonts():
    """Preserve DejaVu when available; resolve the original Linux paths on Windows."""
    original = ImageFont.truetype

    def truetype(font, *args, **kwargs):
        try:
            return original(font, *args, **kwargs)
        except OSError:
            bold = "bold" in str(font).lower()
            candidates = ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
                          "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf")
            for candidate in candidates:
                try:
                    return original(candidate, *args, **kwargs)
                except OSError:
                    continue
            return ImageFont.load_default(size=kwargs.get("size", args[0] if args else 13))

    ImageFont.truetype = truetype
    try:
        yield
    finally:
        ImageFont.truetype = original

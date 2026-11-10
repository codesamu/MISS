"""Load the existing GUIs with simulation devices, without editing their sources."""

from contextlib import contextmanager
import importlib.util
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

if __package__:
    from .adapters import Devices, ReturnToDashboard, desktop_fonts
else:
    from adapters import Devices, ReturnToDashboard, desktop_fonts


PROJECT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / "data"


class Runtime:
    def __init__(self, surface, data_dir=DATA):
        self.surface = surface
        self.data_dir = Path(data_dir)
        self.devices = Devices(surface)
        self.modules = {}

    @contextmanager
    def installed(self):
        with self.devices.installed(), desktop_fonts():
            yield self

    def load(self, name):
        if name in self.modules:
            return self.modules[name]
        path = PROJECT / ("capture-photos/main.py" if name == "photos" else f"display-cam-gui/{name}.py")
        spec = importlib.util.spec_from_file_location(f"miss_sim_{name.replace('-', '_')}", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        # Keep old blocking UI loops responsive to window close and desktop controls.
        module.time = SimpleNamespace(**{key: getattr(time, key) for key in dir(time) if not key.startswith("_")})
        module.time.sleep = self.surface.sleep
        if name == "main":
            module.APP_DIR = self.data_dir / "camera"
            module.DATA_DIR = self.data_dir / "dataset"
            module.SETTINGS_FILE = self.data_dir / "settings.json"
            module.APP_DIR.mkdir(parents=True, exist_ok=True)
            module.subprocess = SimpleNamespace(
                Popen=self.devices.camera_process, PIPE=subprocess.PIPE,
                DEVNULL=subprocess.DEVNULL, TimeoutExpired=subprocess.TimeoutExpired,
            )

            def capture(path, width=480, height=274, timeout_ms=500):
                self.surface.camera_image((width, height)).save(path, format="JPEG")

            module.capture_rpicam = capture
        elif name == "photos":
            module.MjpegCamera = self.devices.camera
        elif name == "live-detection":
            module.camera_class = lambda: self.devices.camera
        elif name == "dashboard":
            def launch(app, script):
                app.lcd.close()
                app.touch.close()
                target = "photos" if Path(script).parent.name == "capture-photos" else Path(script).stem
                try:
                    self.run_app(target)
                except ReturnToDashboard:
                    pass
                finally:
                    self.surface.active_app = "dashboard"
                    self.surface.home_requested = False
                    self.surface.clicks.clear()
                    app.lcd = self.devices.lcd()
                    app.touch = self.devices.touch()

            module.DashboardApp.launch_script = launch
        self.modules[name] = module
        return module

    def run_app(self, name="dashboard"):
        self.surface.active_app = name
        self.surface.clicks.clear()
        module = self.load(name)
        if name == "photos":
            app = module.PhotoCollectorApp(self.data_dir / "photos", interval=5)
            try:
                app.run()
            finally:
                app.close()
        elif name == "live-detection":
            previous = sys.argv
            sys.argv = [str(module.__file__)]
            try:
                module.main()
            finally:
                sys.argv = previous
        else:
            cls = {"dashboard": "DashboardApp", "main": "SmartBinApp", "display-servos": "ServoDisplayApp"}[name]
            getattr(module, cls)().run()

    def run_miss(self, config_path=None):
        from miss_app.app import EventLog, run
        from miss_app.config import DEFAULT_CONFIG, load_config
        from miss_app.servos import TimedSorter
        from miss_app.vision import Observation, predict

        config = load_config(config_path or DEFAULT_CONFIG)
        surface, devices = self.surface, self.devices
        surface.active_app = "miss"
        surface.plate = config.plate

        class DemoVision:
            error = None

            def __init__(self):
                self.next_at = 0
                self.sequence = 0
                self.detector = devices.yolo("simulation", latency=0)

            def start(self):
                pass

            def latest(self):
                now = time.perf_counter()
                if now < self.next_at:
                    return None
                image = surface.camera_image((640, 480))
                detections = predict(self.detector, image, config)
                self.sequence += 1
                self.next_at = now + 0.1
                return Observation(image, detections, now, self.sequence)

            def close(self):
                pass

        sorter = TimedSorter(devices.servo(16), devices.servo(20), config,
                             on_complete=surface.sort_completed)
        vision = DemoVision()
        try:
            run(devices.lcd(), devices.touch(), vision, sorter, config,
                EventLog(self.data_dir / "miss" / "feedback.jsonl", simulated=True), sleep=surface.sleep)
        finally:
            vision.close()
            sorter.close()

"""Exercise the original app workflows through the simulation adapters."""

from contextlib import ExitStack
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import sys

from PIL import Image

from adapters import Devices, ReturnToDashboard, Surface
from runtime import Runtime


class ScriptedSurface(Surface):
    def __init__(self, actions=()):
        super().__init__()
        self.actions = iter(actions)
        self.frames = []

    def show(self, image):
        self.frame = image.copy()
        self.frames.append(image.copy())
        action = next(self.actions, None)
        if action == "home":
            raise ReturnToDashboard()
        if action is not None:
            self.clicks.append(action)

    def sleep(self, seconds):
        self.pump()
        time.sleep(min(seconds, 0.002))


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))

    def runtime(self, surface):
        runtime = Runtime(surface, self.directory)
        self.stack.enter_context(runtime.installed())
        return runtime

    def test_touch_coordinates_match_all_apps_including_corners(self):
        surface = Surface()
        runtime = self.runtime(surface)
        live = runtime.load("live-detection")
        touch = runtime.devices.touch()
        for xy in ((0, 0), (479, 0), (0, 319), (479, 319), (240, 160)):
            surface.clicks.append(xy)
            self.assertEqual(live.touch_position(touch), xy)
            self.assertIsNone(live.touch_position(touch))

    def test_dashboard_launches_servo_app_and_returns(self):
        # Dashboard -> servo menu -> direction menu -> RF -> back -> exit -> dashboard exit.
        surface = ScriptedSurface(((350, 110), (200, 120), (300, 120),
                                   (50, 270), (300, 270), (200, 260)))
        runtime = self.runtime(surface)
        runtime.run_app()
        self.assertIn("GPIO 16: Minimum", surface.events)
        self.assertIn("GPIO 20: Minimum", surface.events)
        self.assertEqual(surface.servos, {16: 0, 20: 0})
        self.assertEqual(len(surface.frames), 6)

    def test_manual_capture_saves_only_simulation_dataset(self):
        # Preview -> shutter flash -> review -> category -> saved -> main menu.
        surface = ScriptedSurface(((300, 295), None, (380, 100), (60, 90), None, "home"))
        runtime = self.runtime(surface)
        app = runtime.load("main").SmartBinApp()
        with self.assertRaises(ReturnToDashboard):
            app.show_camera_view()
        files = list((self.directory / "dataset" / "plastik").glob("*.jpg"))
        self.assertEqual(len(files), 1)
        with Image.open(files[0]) as photo:
            self.assertEqual(photo.size, (1920, 1080))
        app.zoom = 1.4
        app.save_settings()
        self.assertTrue((self.directory / "settings.json").exists())
        self.assertTrue(app.captured_path.is_relative_to(self.directory))

    def test_photo_collector_writes_valid_jpeg_and_stops(self):
        surface = ScriptedSurface((None, None, (400, 295), None))
        runtime = self.runtime(surface)
        module = runtime.load("photos")
        app = module.PhotoCollectorApp(self.directory / "photos", interval=0.001)
        try:
            app.run()
        finally:
            app.close()
        photos = list((self.directory / "photos").glob("*.jpg"))
        self.assertGreaterEqual(len(photos), 1)
        with Image.open(photos[0]) as image:
            self.assertEqual(image.size, (1296, 972))

    def test_live_detection_uses_existing_menu_and_rendering(self):
        surface = Surface()
        runtime = self.runtime(surface)
        live = runtime.load("live-detection")
        source = surface.camera_image((640, 480))
        detector = runtime.devices.yolo("unused.pt")
        state = live.MultiClassStabilizer(0.6, 0.6, 2, 4)
        results = detector.predict(source)
        self.assertEqual(state.update(results), {})
        self.assertEqual(state.update(results), {"plastic-bottle": 0.85})
        image = live.render(source, results, 0.6, {"plastic-bottle": 0.85}, 10, live.load_font())
        self.assertEqual(image.size, (480, 320))
        surface.scene = "Beide"
        self.assertEqual(len(detector.predict(source)[0].boxes), 2)
        surface.confidence = 0.3
        self.assertEqual(detector.predict(source, conf=0.6)[0].boxes, [])
        surface.custom_image = source
        surface.confidence = 0.9
        self.assertEqual(detector.predict(source)[0].boxes, [])

    def test_model_selection_cancel_returns_to_dashboard(self):
        surface = ScriptedSurface()
        runtime = self.runtime(surface)
        live = runtime.load("live-detection")
        # Model menu deliberately ignores the dashboard launch touch. Send cancel after release.
        calls = 0
        original_sleep = surface.sleep

        def sleep(seconds):
            nonlocal calls
            calls += 1
            if calls == 1:
                surface.clicks.append((400, 300))
            original_sleep(seconds)

        live.time.sleep = sleep
        self.assertIsNone(live.choose_model(runtime.devices.lcd(), runtime.devices.touch(),
                                           [Path("demo.pt")], live.load_font()))

    def test_live_app_runs_complete_frame_loop_without_torch_or_camera(self):
        surface = ScriptedSurface()
        runtime = self.runtime(surface)
        live = runtime.load("live-detection")
        # Only the existing CLI's file-existence check uses this file; the fake
        # detector never reads weights or imports a real inference framework.
        model = self.directory / "test-double.pt"
        model.write_bytes(b"simulation test fixture")
        with patch.object(sys, "argv", [str(live.__file__), "--model", str(model), "--max-frames", "2"]):
            self.assertEqual(live.main(), 0)
        self.assertEqual(len(surface.frames), 4)  # Two loading screens, two results.
        self.assertEqual(surface.frames[-1].size, (480, 320))

    def test_window_home_interrupts_camera_before_next_frame(self):
        surface = Surface()
        runtime = self.runtime(surface)
        surface.active_app = "photos"
        surface.home_requested = True
        camera = runtime.devices.camera(640, 480, 30, "demo")
        with self.assertRaises(ReturnToDashboard):
            camera.latest()
        self.assertFalse(surface.home_requested)

    def test_shared_main_program_sorts_and_returns_after_feedback(self):
        clock = [0.0]

        class InteractiveSurface(Surface):
            reviewed = False

            def sleep(self, seconds):
                self.pump()
                clock[0] += seconds

            def show(self, image):
                super().show(image)
                is_feedback = self.workflow_state == "feedback"
                if is_feedback and not self.reviewed and clock[0] - self.workflow_since > 0.25:
                    self.reviewed = True
                    self.clicks.append((65, 160))
                elif self.reviewed and not is_feedback:
                    raise ReturnToDashboard()

        surface = InteractiveSurface()
        runtime = self.runtime(surface)
        with patch("time.perf_counter", side_effect=lambda: clock[0]):
            with self.assertRaises(ReturnToDashboard):
                runtime.run_miss()
        self.assertTrue(surface.reviewed)
        self.assertEqual(surface.scene, "Kein Objekt")
        import json
        records = [json.loads(line) for line in (self.directory / "miss" / "feedback.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([event["event"] for event in records], ["sorted", "feedback"])
        self.assertTrue(records[-1]["correct"])
        self.assertTrue(records[-1]["simulated"])


if __name__ == "__main__":
    unittest.main()

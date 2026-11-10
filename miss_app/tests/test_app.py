from types import SimpleNamespace
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image

from miss_app.app import run
from miss_app.config import Config
from miss_app.core import Detection
from miss_app.vision import BackgroundVision, Observation


class StopLoop(BaseException):
    pass


class ApplicationTests(unittest.TestCase):
    def test_touch_during_final_servo_tick_is_not_a_vote(self):
        clock = [0.0]
        records = []
        frames = []
        config = Config(stable_seconds=0.1, stable_frames=2)

        class Sorter:
            busy = False

            def start(self, direction, now):
                self.busy = True

            def update(self, now):
                self.busy = False

        class Touch:
            def read_touch_data(self):
                pass

            def get_touch_xy(self):
                # First touch is made at the last servo tick and then held.
                # Only the second, fresh touch on the visible feedback may vote.
                if round(clock[0], 1) in (0.2, 0.3, 0.5):
                    return 1, [{"x": 319 - 160, "y": 479 - 65}]
                return 0, []

        class Vision:
            error = None
            sequence = 0

            def start(self):
                pass

            def latest(self):
                self.sequence += 1
                items = [Detection("plastic-bottle", 0.9, (0.3, 0.3, 0.5, 0.7))] if clock[0] < 0.2 else []
                return Observation(Image.new("RGB", (640, 480), "#303b43"), items, clock[0], self.sequence)

        def sleep(seconds):
            clock[0] = round(clock[0] + 0.1, 1)
            if clock[0] > 0.6:
                raise StopLoop()

        with patch("miss_app.app.time.perf_counter", side_effect=lambda: clock[0]):
            with self.assertRaises(StopLoop):
                run(SimpleNamespace(show_image=frames.append), Touch(), Vision(), Sorter(), config,
                    lambda event: records.append((clock[0], event)), sleep=sleep)
        self.assertEqual([(at, event["event"]) for at, event in records], [(0.2, "sorted"), (0.5, "feedback")])
        self.assertTrue(records[-1][1]["correct"])
        self.assertTrue(all(frame.size == (480, 320) for frame in frames))

    def test_background_inference_does_not_block_ui_reader(self):
        entered, release = threading.Event(), threading.Event()

        class Camera:
            def start(self):
                pass

            def latest(self, timeout):
                return SimpleNamespace(image=Image.new("RGB", (640, 480)))

            def close(self):
                release.set()

        class Detector:
            def predict(self, image, **kwargs):
                entered.set()
                release.wait(2)
                return [SimpleNamespace(boxes=[], names={})]

        vision = BackgroundVision(Camera(), Detector(), Config())
        vision.start()
        try:
            self.assertTrue(entered.wait(1))
            start = time.monotonic()
            self.assertIsNone(vision.latest())
            self.assertLess(time.monotonic() - start, 0.1)
        finally:
            release.set()
            vision.close()


if __name__ == "__main__":
    unittest.main()

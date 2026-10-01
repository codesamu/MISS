import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image


SCRIPT = Path(__file__).with_name("live-detection.py")
SPEC = importlib.util.spec_from_file_location("live_detection", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


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


class LiveDetectionTests(unittest.TestCase):
    def test_detection_state_uses_hysteresis(self):
        state = MODULE.DetectionStabilizer(0.55, 0.30, 2, 4)

        self.assertFalse(state.update(0.70))
        self.assertTrue(state.update(0.60))
        self.assertTrue(state.update(0.40))
        self.assertTrue(state.update(0.10))
        self.assertTrue(state.update(0.00))
        self.assertTrue(state.update(0.20))
        self.assertFalse(state.update(0.00))

    def test_render_draws_detection_box(self):
        box = SimpleNamespace(
            conf=Scalar(0.80),
            cls=Scalar(0),
            xyxy=[Coordinates([100, 100, 400, 350])],
        )
        result = SimpleNamespace(boxes=[box], names={0: "PET"})
        frame = Image.new("RGB", (640, 480), "black")

        rendered = MODULE.render(
            frame,
            [result],
            box_confidence=0.30,
            detected=True,
            confidence=0.80,
            fps=2.0,
            font=MODULE.load_font(),
        )

        self.assertEqual(rendered.size, (480, 320))
        self.assertIn((48, 238, 128), set(rendered.getdata()))

    def test_existing_classifiers_are_not_auto_selected(self):
        selected = MODULE.find_models()
        self.assertFalse(any("/runs/classify/" in path.as_posix() for path in selected))


if __name__ == "__main__":
    unittest.main()

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
            active={"PET": 0.80},
            fps=2.0,
            font=MODULE.load_font(),
        )

        self.assertEqual(rendered.size, (480, 320))
        self.assertIn((48, 238, 128), set(rendered.getdata()))

    def test_zero_threshold_does_not_confirm_missing_detections(self):
        state = MODULE.DetectionStabilizer(0.0, 0.0, 1, 1)
        self.assertFalse(state.update(0.0))
        self.assertTrue(state.update(0.5))
        self.assertFalse(state.update(0.0))

    def test_classes_are_confirmed_and_released_independently(self):
        state = MODULE.MultiClassStabilizer(0.60, 0.40, 2, 2)

        def results(*class_ids):
            return [SimpleNamespace(
                boxes=[SimpleNamespace(cls=Scalar(i), conf=Scalar(0.8)) for i in class_ids],
                names={0: " aluminum-can", 1: "plastic-bottle"},
            )]

        # Abwechselnde Klassen duerfen sich nicht gegenseitig bestaetigen.
        self.assertEqual(state.update(results(0)), {})
        self.assertEqual(state.update(results(1)), {})
        self.assertEqual(state.update(results(0)), {})
        self.assertEqual(state.update(results(0)), {"aluminum-can": 0.8})
        self.assertEqual(state.update(results(1)), {"aluminum-can": 0.0})
        self.assertEqual(state.update(results(1)), {"plastic-bottle": 0.8})
        state.update(results(0, 1))
        self.assertEqual(state.update(results(0, 1)), {
            "aluminum-can": 0.8, "plastic-bottle": 0.8,
        })
        state.update(results())
        self.assertEqual(state.update(results()), {})

    def test_render_uses_distinct_colors_for_classes(self):
        result = SimpleNamespace(names={0: "aluminum-can", 1: "plastic-bottle"}, boxes=[
            SimpleNamespace(conf=Scalar(0.8), cls=Scalar(i),
                            xyxy=[Coordinates([100 + i * 250, 200, 200 + i * 250, 350])])
            for i in (0, 1)
        ])
        rendered = MODULE.render(Image.new("RGB", (640, 480)), [result], 0.6,
                                 {"aluminum-can": 0.8, "plastic-bottle": 0.8},
                                 2.0, MODULE.load_font())
        pixels = set(rendered.getdata())
        self.assertIn((48, 238, 128), pixels)
        self.assertIn((255, 204, 51), pixels)

    def test_touch_menu_changes_page_and_selects_run(self):
        paths = [Path(f"run_{i}/train/weights/best.pt") for i in range(5)]
        positions = [(50, 70), None, (200, 300), (200, 300), None, (50, 70)]
        lcd = Mock()
        with patch.object(MODULE, "touch_position", side_effect=positions), \
                patch.object(MODULE.time, "sleep"):
            selected = MODULE.choose_model(lcd, Mock(), paths, MODULE.load_font())
        self.assertEqual(selected, paths[4])
        self.assertEqual(lcd.show_image.call_count, 2)
        self.assertEqual(MODULE.model_title(selected), "run_4 / best.pt")

    def test_touch_menu_can_cancel(self):
        with patch.object(MODULE, "touch_position", side_effect=[None, (400, 300)]), \
                patch.object(MODULE.time, "sleep"):
            self.assertIsNone(MODULE.choose_model(
                Mock(), Mock(), [Path("pet.pt")], MODULE.load_font()
            ))

    def test_existing_classifiers_are_not_auto_selected(self):
        selected = MODULE.find_models()
        self.assertFalse(any("/runs/classify/" in path.as_posix() for path in selected))


if __name__ == "__main__":
    unittest.main()

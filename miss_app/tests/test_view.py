from types import SimpleNamespace
import unittest

from PIL import Image

from miss_app.config import Config
from miss_app.core import Detection, State, Workflow
from miss_app.view import Renderer, render


class PressAnimationTests(unittest.TestCase):
    def test_readiness_ring_updates_and_resets_on_an_unchanged_camera_background(self):
        config = Config()
        machine = Workflow(config, SimpleNamespace(start=lambda *args: None))
        camera = Image.new("RGB", (640, 480), "#243940")
        bottle = Detection("plastic-bottle", 0.9, (0.3, 0.3, 0.5, 0.7))
        detections = [bottle]
        renderer = Renderer()
        machine.observe(detections, 0, 0, 0)
        first = renderer.render(camera, detections, machine, config, 0)
        machine.observe(detections, 0.5, 1, 0.5)
        progressed = renderer.render(camera, detections, machine, config, 0.6)
        ring = (214, 214, 266, 266)
        self.assertNotEqual(first.crop(ring).tobytes(), progressed.crop(ring).tobytes())
        moved = Detection("plastic-bottle", 0.9, (0.45, 0.3, 0.65, 0.7))
        machine.observe([moved], 0.7, 2, 0.7)
        reset = renderer.render(camera, detections, machine, config, 0.7)
        self.assertEqual(first.crop(ring).tobytes(), reset.crop(ring).tobytes())

    def test_each_vote_animates_then_returns_to_live_without_holding_workflow(self):
        for correct in (True, False):
            with self.subTest(correct=correct):
                config = Config()
                machine = SimpleNamespace(state=State.FEEDBACK, selected="plastic-bottle",
                                          feedback_started=0, deadline=10, message="")
                camera = Image.new("RGB", (640, 480), "#243940")
                detections = []
                renderer = Renderer()
                before = renderer.render(camera, detections, machine, config, 1)
                renderer.acknowledge(correct, 1.1)
                machine.state = State.LIVE  # Vote is already accepted by the workflow.
                first = renderer.render(camera, detections, machine, config, 1.15)
                rebound = renderer.render(camera, detections, machine, config, 1.3)
                self.assertNotEqual(first.tobytes(), before.tobytes())
                self.assertNotEqual(first.tobytes(), rebound.tobytes())
                self.assertEqual(machine.state, State.LIVE)
                held = renderer.render(camera, detections, machine, config, 2.1)
                self.assertTrue(renderer.holding_result(2.1))
                self.assertNotEqual(held.tobytes(), render(camera, detections, machine, config, 2.1).tobytes())
                after = renderer.render(camera, detections, machine, config, 3)
                self.assertFalse(renderer.holding_result(3))
                expected = render(camera, detections, machine, config, 3)
                self.assertEqual(after.tobytes(), expected.tobytes())


if __name__ == "__main__":
    unittest.main()

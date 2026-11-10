import json
from pathlib import Path
import tempfile
import unittest

from miss_app.app import EventLog
from miss_app.config import Config, load_config
from miss_app.core import Detection, State, Workflow
from miss_app.servos import TimedSorter
from miss_app.view import DOWN, UP, feedback, vote_at


BOTTLE = Detection("plastic-bottle", 0.9, (0.3, 0.3, 0.5, 0.7))
CAN = Detection("aluminum-can", 0.9, (0.55, 0.4, 0.7, 0.7))


class FakeSorter:
    def __init__(self):
        self.busy = False
        self.starts = []

    def start(self, direction, now):
        self.busy = True
        self.starts.append(direction)

    def update(self, now):
        pass

    def cancel(self):
        self.busy = False


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(stable_seconds=0.5, stable_frames=3, clear_seconds=0.3)
        self.sorter = FakeSorter()
        self.events = []
        self.machine = Workflow(self.config, self.sorter, self.events.append)
        self.sequence = 0

    def see(self, items, time, age=0):
        self.sequence += 1
        self.machine.observe(items, time - age, self.sequence, time)

    def confirm(self, item=BOTTLE, start=0):
        for time in (start, start + 0.3, start + 0.6):
            self.see([item], time)

    def finish_sort(self, at=2):
        self.sorter.busy = False
        self.machine.tick(at)

    def test_single_stable_object_starts_once(self):
        self.confirm()
        self.assertEqual(self.machine.state, State.SORTING)
        self.assertEqual(self.sorter.starts, ["rf"])
        self.confirm(start=1)
        self.assertEqual(len(self.sorter.starts), 1)

    def test_readiness_progress_requires_actual_new_observations(self):
        self.assertIsNone(self.machine.stability_progress(0))
        self.see([BOTTLE], 0)
        self.assertEqual(self.machine.stability_progress(0), 0)
        self.see([BOTTLE], 0.3)
        self.assertAlmostEqual(self.machine.stability_progress(0.3), 0.6)
        self.assertAlmostEqual(self.machine.stability_progress(1.5), 0.6)
        self.assertIsNone(self.machine.stability_progress(3))

    def test_progress_resets_on_motion_and_disappears_for_multiple_objects(self):
        self.see([BOTTLE], 0)
        self.see([BOTTLE], 0.3)
        moved = Detection("plastic-bottle", 0.9, (0.45, 0.3, 0.65, 0.7))
        self.see([moved], 0.4)
        self.assertEqual(self.machine.stability_progress(0.4), 0)
        self.see([BOTTLE, CAN], 0.5)
        self.assertIsNone(self.machine.stability_progress(0.5))

    def test_progress_does_not_finish_while_required_frames_are_missing(self):
        self.config.stable_frames = 10
        self.see([BOTTLE], 0)
        self.see([BOTTLE], 0.7)
        self.assertAlmostEqual(self.machine.stability_progress(0.7), 0.2)
        self.assertFalse(self.sorter.starts)

    def test_progress_is_hidden_when_uncertain_outside_plate_or_sorting(self):
        for item in (Detection("plastic-bottle", 0.4, BOTTLE.box),
                     Detection("plastic-bottle", 0.9, (0.1, 0.3, 0.3, 0.7))):
            self.see([item], self.sequence)
            self.assertIsNone(self.machine.stability_progress(self.sequence))
        self.confirm(start=3)
        self.assertEqual(self.machine.state, State.SORTING)
        self.assertIsNone(self.machine.stability_progress(3.6))

    def test_two_objects_of_same_class_block_sorting(self):
        second = Detection("plastic-bottle", 0.8, (0.55, 0.4, 0.7, 0.7))
        for time in (0, 0.3, 0.7, 1.3):
            self.see([BOTTLE, second], time)
        self.assertFalse(self.sorter.starts)
        self.assertIn("nur einen", self.machine.message)

    def test_second_weak_object_also_blocks(self):
        weak = Detection("aluminum-can", 0.3, CAN.box)
        for time in (0, 0.3, 0.7):
            self.see([BOTTLE, weak], time)
        self.assertFalse(self.sorter.starts)

    def test_partial_and_outside_objects_do_not_sort(self):
        for box in ((0.1, 0.3, 0.3, 0.7), (0.01, 0.3, 0.1, 0.7)):
            self.confirm(Detection("plastic-bottle", 0.9, box), start=self.sequence)
        self.assertFalse(self.sorter.starts)

    def test_object_fully_outside_plate_does_not_block_single_inside(self):
        outside = Detection("aluminum-can", 0.9, (0.01, 0.1, 0.1, 0.5))
        for time in (0, 0.3, 0.6):
            self.see([BOTTLE, outside], time)
        self.assertEqual(self.sorter.starts, ["rf"])

    def test_moving_box_and_changing_class_restart_stability(self):
        moved = Detection("plastic-bottle", 0.9, (0.45, 0.3, 0.65, 0.7))
        for time, item in ((0, BOTTLE), (0.3, moved), (0.6, CAN), (0.9, BOTTLE)):
            self.see([item], time)
        self.assertFalse(self.sorter.starts)

    def test_uncertain_or_unmapped_class_never_sorts(self):
        self.confirm(Detection("plastic-bottle", 0.5, BOTTLE.box))
        self.confirm(Detection("glass", 0.95, BOTTLE.box), start=1)
        self.assertFalse(self.sorter.starts)

    def test_stale_duplicate_and_invalid_frames_never_confirm(self):
        for time in (0, 0.3, 0.6):
            self.machine.observe([BOTTLE], 0, 1, time)
        self.assertFalse(self.sorter.starts)
        for time in (4, 5, 6):
            self.see([BOTTLE], time, age=3)
        self.confirm(Detection("plastic-bottle", float("nan"), BOTTLE.box), start=7)
        self.assertFalse(self.sorter.starts)

    def test_gap_resets_candidate(self):
        self.see([BOTTLE], 0)
        self.see([BOTTLE], 0.3)
        self.see([BOTTLE], 4)
        self.assertFalse(self.sorter.starts)

    def test_countdown_starts_after_motors_finish_and_expires_without_new_frames(self):
        self.confirm()
        self.machine.tick(7)
        self.assertEqual(self.machine.state, State.SORTING)
        self.finish_sort(at=8)
        self.assertEqual(self.machine.deadline, 18)
        self.machine.tick(17.99)
        self.assertEqual(self.machine.state, State.FEEDBACK)
        self.machine.tick(18)
        self.assertEqual(self.machine.state, State.LIVE)
        self.assertEqual([e["event"] for e in self.events], ["sorted", "feedback"])
        self.assertIsNone(self.events[-1]["correct"])

    def test_vote_exits_immediately_and_is_recorded_once(self):
        self.confirm()
        self.finish_sort()
        self.assertTrue(self.machine.vote(False, 2.1))
        self.assertFalse(self.machine.vote(True, 2.2))
        self.assertEqual(self.machine.state, State.LIVE)
        self.assertFalse(self.events[-1]["correct"])
        self.assertEqual(self.events[0]["cycle_id"], self.events[1]["cycle_id"])

    def test_late_vote_is_ignored_and_timeout_has_no_rating(self):
        self.confirm()
        self.finish_sort()
        self.assertFalse(self.machine.vote(True, 12))
        self.machine.tick(12)
        self.assertIsNone(self.events[-1]["correct"])

    def test_lingering_item_requires_empty_plate_before_next_sort(self):
        self.confirm()
        self.finish_sort()
        self.machine.vote(True, 2.1)
        self.confirm(start=3)
        self.assertEqual(len(self.sorter.starts), 1)
        self.see([], 4)
        self.see([], 4.4)
        self.assertFalse(self.machine.needs_clear)
        self.confirm(start=5)
        self.assertEqual(len(self.sorter.starts), 2)

    def test_empty_frames_before_servo_completion_cannot_rearm(self):
        self.confirm()
        self.see([], 1)
        self.see([], 1.5)
        self.finish_sort()
        self.see([], 2.2, age=1)
        self.assertTrue(self.machine.needs_clear)

    def test_empty_plate_can_be_verified_during_feedback(self):
        self.confirm()
        self.finish_sort()
        self.see([], 2.1)
        self.see([], 2.5)
        self.assertFalse(self.machine.needs_clear)
        self.machine.vote(True, 2.6)
        self.confirm(CAN, start=3)
        self.assertEqual(self.sorter.starts, ["rf", "lf"])

    def test_fault_stops_motors_and_cannot_be_rearmed(self):
        self.confirm()
        self.machine.fail("camera disconnected")
        self.confirm(start=5)
        self.assertEqual(self.machine.state, State.FAULT)
        self.assertFalse(self.sorter.busy)
        self.assertEqual(len(self.sorter.starts), 1)

    def test_feedback_animation_changes_and_both_touch_targets_work(self):
        self.confirm()
        self.finish_sort()
        first = feedback(self.machine, self.config, 2)
        second = feedback(self.machine, self.config, 2.4)
        self.assertEqual(first.size, (480, 320))
        self.assertNotEqual(first.tobytes(), second.tobytes())
        self.assertIs(vote_at((UP[0] + 10, UP[1] + 10)), True)
        self.assertIs(vote_at((DOWN[0] + 10, DOWN[1] + 10)), False)
        self.assertIsNone(vote_at((240, 160)))


class ServoTests(unittest.TestCase):
    def test_nonblocking_sequence_respects_real_delays_after_late_ticks(self):
        moves = []

        class Servo:
            def __init__(self, name):
                self.name = name

            def min(self):
                moves.append((self.name, -1))

            def max(self):
                moves.append((self.name, 1))

            def mid(self):
                moves.append((self.name, 0))

        sorter = TimedSorter(Servo("h"), Servo("v"), Config())
        moves.clear()
        sorter.start("lf", 0)
        self.assertEqual(moves, [("h", 1)])
        sorter.update(0.69)
        self.assertEqual(len(moves), 1)
        sorter.update(5)  # Late tick may execute only the next physical step.
        self.assertEqual(moves, [("h", 1), ("v", -1)])
        sorter.update(5.1)
        self.assertEqual(len(moves), 2)
        sorter.update(6.8)
        sorter.update(7.6)
        sorter.update(8.4)
        self.assertEqual(moves, [("h", 1), ("v", -1), ("v", 0), ("h", 0)])
        self.assertFalse(sorter.busy)


class ConfigurationAndLogTests(unittest.TestCase):
    def test_default_config_and_invalid_plate(self):
        self.assertEqual(load_config().feedback_seconds, 10)
        with self.assertRaises(ValueError):
            Config(plate=(0.9, 0, 0.2, 1))
        with self.assertRaises(ValueError):
            Config(routes={"plastic-bottle": "unknown"})

    def test_feedback_is_saved_with_simulation_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feedback.jsonl"
            log = EventLog(path, simulated=True)
            log({"event": "feedback", "class": "plastic-bottle", "correct": False})
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(record["simulated"])
            self.assertFalse(record["correct"])
            self.assertIn("timestamp", record)


if __name__ == "__main__":
    unittest.main()

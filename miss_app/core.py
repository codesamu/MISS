"""Time-based sorting workflow. No display, GPIO, camera or ML imports."""

from dataclasses import dataclass
from enum import Enum
import math
import uuid


class State(str, Enum):
    LIVE = "live"
    SORTING = "sorting"
    FEEDBACK = "feedback"
    FAULT = "fault"


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    box: tuple  # Normalized x1, y1, x2, y2 in the original camera image.

    def valid(self):
        if len(self.box) != 4 or not math.isfinite(self.confidence):
            return False
        if not all(math.isfinite(v) for v in self.box):
            return False
        x1, y1, x2, y2 = self.box
        return 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1 and 0 <= self.confidence <= 1


def intersection(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def iou(a, b):
    overlap = intersection(a, b)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - overlap
    return overlap / union if union > 0 else 0


class Workflow:
    def __init__(self, config, sorter, record=lambda event: None):
        self.config, self.sorter, self.record = config, sorter, record
        self.state = State.LIVE
        self.message = ""
        self.selected = None
        self.direction = None
        self.cycle_id = None
        self.deadline = None
        self.feedback_started = None
        self.needs_clear = False
        self.motion_finished = float("-inf")
        self._candidate = None
        self._since = None
        self._hits = 0
        self._clear_since = None
        self._last_sequence = -1
        self._last_capture = None

    def _reset_candidate(self):
        self._candidate = None
        self._since = None
        self._hits = 0

    def stability_progress(self, now):
        """Confirmed readiness, limited by both new frames and stable duration."""
        if (self.state != State.LIVE or self.needs_clear or self._candidate is None
                or self._since is None or self._last_capture is None
                or not math.isfinite(now) or now - self._last_capture > self.config.max_observation_age):
            return None
        duration = max(0, self._last_capture - self._since) / self.config.stable_seconds
        frames = self._hits / self.config.stable_frames
        return min(1.0, duration, frames)

    def observe(self, detections, captured_at, sequence, now):
        if self.state in (State.SORTING, State.FAULT) or sequence <= self._last_sequence:
            return
        self._last_sequence = sequence
        if (not math.isfinite(captured_at) or captured_at > now or now - captured_at > self.config.max_observation_age
                or (self._last_capture is not None and captured_at <= self._last_capture)):
            self._reset_candidate()
            self._clear_since = None
            return
        if self._last_capture is not None and captured_at - self._last_capture > self.config.max_observation_age:
            self._reset_candidate()
            self._clear_since = None
        self._last_capture = captured_at
        if any(not item.valid() for item in detections):
            self._reset_candidate()
            self._clear_since = None
            self.message = "Kamerabild bitte prüfen"
            return
        present = [d for d in detections if d.confidence >= self.config.presence_confidence
                   and intersection(d.box, self.config.plate) > 0]
        if self.needs_clear:
            if captured_at <= self.motion_finished:
                return
            if present:
                self._clear_since = None
            else:
                if self._clear_since is None:
                    self._clear_since = captured_at
                if captured_at - self._clear_since >= self.config.clear_seconds:
                    self.needs_clear = False
                    self._clear_since = None
            if self.needs_clear:
                if self.state == State.LIVE:
                    self.message = "Sortierplatte bitte freimachen"
                return
        if self.state != State.LIVE:
            return
        self.message = ""
        if len(present) != 1:
            self._reset_candidate()
            if len(present) > 1:
                self.message = "Bitte nur einen Gegenstand einlegen"
            return
        item = present[0]
        x1, y1, x2, y2 = item.box
        px1, py1, px2, py2 = self.config.plate
        if not (px1 <= x1 < x2 <= px2 and py1 <= y1 < y2 <= py2):
            self._reset_candidate()
            self.message = "Gegenstand mittig auf die Platte legen"
            return
        if item.confidence < self.config.sort_confidence:
            self._reset_candidate()
            self.message = "Gegenstand wird geprüft"
            return
        if item.label not in self.config.routes:
            self._reset_candidate()
            self.message = "Für diesen Gegenstand fehlt eine Sortierzuordnung"
            return
        if self._candidate is None or item.label != self._candidate.label or iou(item.box, self._candidate.box) < self.config.stable_iou:
            self._candidate = item
            self._since = captured_at
            self._hits = 1
        else:
            self._hits += 1
        self.message = "Gegenstand wird geprüft"
        if self._hits >= self.config.stable_frames and captured_at - self._since >= self.config.stable_seconds:
            self.selected = item.label
            self.direction = self.config.routes[item.label]
            self.cycle_id = uuid.uuid4().hex
            self.sorter.start(self.direction, now)
            self.state = State.SORTING
            self.needs_clear = True
            self._clear_since = None
            self._reset_candidate()
            self.message = "Wird sortiert …"

    def tick(self, now):
        if self.state == State.SORTING:
            self.sorter.update(now)
            if not self.sorter.busy:
                self.motion_finished = now
                self.feedback_started = now
                self.deadline = now + self.config.feedback_seconds
                self.state = State.FEEDBACK
                self.record(self._event("sorted"))
        elif self.state == State.FEEDBACK and now >= self.deadline:
            self._finish(None)
        elif self.state == State.LIVE and self._last_capture is not None and now - self._last_capture > self.config.max_observation_age:
            self._reset_candidate()
            self._clear_since = None

    def _event(self, kind, **extra):
        return {"event": kind, "cycle_id": self.cycle_id, "class": self.selected,
                "direction": self.direction, **extra}

    def vote(self, correct, now):
        if self.state != State.FEEDBACK or now >= self.deadline:
            return False
        self._finish(bool(correct))
        return True

    def _finish(self, correct):
        self.record(self._event("feedback", correct=correct))
        self.state = State.LIVE
        self.deadline = None
        self._reset_candidate()
        self.message = "Sortierplatte bitte freimachen" if self.needs_clear else ""

    def fail(self, reason):
        self.state = State.FAULT
        self.message = str(reason)
        self.sorter.cancel()

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

from .core import State, Workflow
from .view import Renderer, vote_at


class EventLog:
    def __init__(self, path, simulated=False):
        self.path = Path(path)
        self.simulated = simulated

    def __call__(self, event):
        record = {"timestamp": datetime.now(timezone.utc).isoformat(),
                  "simulated": self.simulated, **event}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def touch_position(touch):
    touch.read_touch_data()
    count, points = touch.get_touch_xy() or (0, [])
    return (479 - points[0]["y"], 319 - points[0]["x"]) if count and points else None


def run(display, touch, vision, sorter, config, log, sleep=time.sleep):
    machine = Workflow(config, sorter, log)
    frame, detections = None, []
    pressed = False
    started_at = time.perf_counter()
    last_packet = None
    renderer = Renderer()
    vision.start()
    while True:
        frame_started = time.perf_counter()
        point = touch_position(touch)
        now = time.perf_counter()
        # Drain touches in every state so a touch made during sorting cannot vote.
        fresh_press = point is not None and not pressed
        pressed = point is not None
        try:
            feedback_was_visible = machine.state == State.FEEDBACK
            machine.tick(now)
            if fresh_press and feedback_was_visible and machine.state == State.FEEDBACK and renderer.can_vote(now):
                answer = vote_at(point)
                if answer is not None:
                    if machine.vote(answer, now):
                        renderer.acknowledge(answer, now)
            packet = vision.latest()
            if packet is not None:
                now = time.perf_counter()
                frame, detections = packet.frame, packet.detections
                last_packet = now
                if machine.state != State.LIVE or not renderer.holding_result(now):
                    machine.observe(detections, packet.captured_at, packet.sequence, now)
            if machine.state != State.FAULT:
                if vision.error is not None:
                    raise RuntimeError(str(vision.error))
                if now - (last_packet if last_packet is not None else started_at) > (10 if last_packet is not None else 20):
                    raise RuntimeError("Keine aktuellen Erkennungsbilder verfügbar.")
        except Exception as error:
            print(f"MISS angehalten: {error}", file=sys.stderr, flush=True)
            machine.fail(str(error))
        state_observer = getattr(display, "set_state", None)
        if state_observer:
            state_observer(machine.state, now)
        pointer = getattr(display, "pointer", point)
        display.show_image(renderer.render(frame, detections, machine, config, time.perf_counter(), pointer))
        # Spend the remaining frame budget waiting; rendering time is not added to it.
        sleep(max(0, 1 / 60 - (time.perf_counter() - frame_started)))

"""Background camera/inference worker. The UI and servo timer never wait for YOLO."""

from dataclasses import dataclass
import queue
import threading
import time

from .core import Detection


@dataclass
class Observation:
    frame: object
    detections: list
    captured_at: float
    sequence: int


def predict(detector, image, config):
    result = detector.predict(image, conf=config.presence_confidence, imgsz=640,
                              device="cpu", verbose=False, save=False)[0]
    detections = []
    if result.boxes is not None:
        for box in result.boxes:
            name = result.names[int(box.cls.item())].strip()
            xy = box.xyxy[0].tolist()
            normalized = tuple(max(0, min(1, value / (image.width if i % 2 == 0 else image.height)))
                               for i, value in enumerate(xy))
            detections.append(Detection(name, float(box.conf.item()), normalized))
    return detections


class BackgroundVision:
    def __init__(self, camera, detector, config):
        self.camera, self.detector, self.config = camera, detector, config
        self._queue = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self.error = None
        self._thread = None

    def start(self):
        self.camera.start()
        self._thread = threading.Thread(target=self._run, name="miss-inference", daemon=True)
        self._thread.start()

    def _run(self):
        sequence = 0
        last_frame = time.perf_counter()
        started = False
        try:
            while not self._stop.is_set():
                frame = self.camera.latest(timeout=0.1)
                if frame is None:
                    if self.camera.failed():
                        raise RuntimeError("Kameraprozess beendet: " + self.camera.failure_reason())
                    if time.perf_counter() - last_frame > (10 if started else 15):
                        raise RuntimeError("Kamera liefert keine Bilder.")
                    continue
                captured_at = time.perf_counter()
                source = frame.image.convert("RGB")
                detections = predict(self.detector, source, self.config)
                sequence += 1
                packet = Observation(source, detections, captured_at, sequence)
                if self._queue.full():
                    try:
                        self._queue.get_nowait()
                    except queue.Empty:
                        pass
                self._queue.put_nowait(packet)
                last_frame = time.perf_counter()
                started = True
        except Exception as error:
            self.error = error

    def latest(self):
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        self.camera.close()

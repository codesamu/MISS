from dataclasses import dataclass, field, fields
import json
import math
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = Path(__file__).with_name("config.json")
DIRECTIONS = {"rf": (-1, -1), "lf": (1, -1), "lb": (-1, 1), "rb": (1, 1)}


@dataclass
class Config:
    model: str = "YOLO/pet.pt"
    plate: tuple = (0.18, 0.16, 0.82, 0.88)
    routes: dict = field(default_factory=lambda: {"plastic-bottle": "rf", "aluminum-can": "lf"})
    labels: dict = field(default_factory=lambda: {"plastic-bottle": "Plastikflasche", "aluminum-can": "Aludose"})
    presence_confidence: float = 0.25
    sort_confidence: float = 0.6
    stable_seconds: float = 1.0
    stable_frames: int = 3
    stable_iou: float = 0.85
    clear_seconds: float = 0.5
    feedback_seconds: float = 10.0
    max_observation_age: float = 2.5
    servo_settle_seconds: float = 0.7
    drop_seconds: float = 1.0
    show_plate: bool = False

    def __post_init__(self):
        self.plate = tuple(self.plate)
        if len(self.plate) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in self.plate):
            raise ValueError("plate muss vier endliche Koordinaten enthalten.")
        x1, y1, x2, y2 = self.plate
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("plate muss [links, oben, rechts, unten] zwischen 0 und 1 sein.")
        if not 0 < self.presence_confidence <= self.sort_confidence <= 1:
            raise ValueError("Confidence: 0 < presence_confidence <= sort_confidence <= 1.")
        if not 0 < self.stable_iou <= 1:
            raise ValueError("stable_iou muss zwischen 0 und 1 liegen.")
        if not isinstance(self.stable_frames, int) or self.stable_frames < 2:
            raise ValueError("stable_frames muss eine ganze Zahl ab 2 sein.")
        for name in ("stable_seconds", "clear_seconds", "feedback_seconds", "max_observation_age", "servo_settle_seconds", "drop_seconds"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} muss positiv und endlich sein.")
        if not isinstance(self.routes, dict) or any(v not in DIRECTIONS for v in self.routes.values()):
            raise ValueError("routes darf nur lf, rf, lb und rb zuordnen.")
        if not isinstance(self.labels, dict) or not all(isinstance(v, str) for v in self.labels.values()):
            raise ValueError("labels muss Anzeigenamen enthalten.")

    @property
    def model_path(self):
        path = Path(self.model)
        return path if path.is_absolute() else PROJECT / path


def load_config(path=DEFAULT_CONFIG):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    unknown = set(data) - {f.name for f in fields(Config)}
    if unknown:
        raise ValueError("Unbekannte Einstellungen: " + ", ".join(sorted(unknown)))
    return Config(**data)

"""Non-blocking version of the project's two-servo movement sequence."""

from .config import DIRECTIONS


class TimedSorter:
    def __init__(self, horizontal, vertical, config, on_complete=lambda: None):
        self.horizontal, self.vertical = horizontal, vertical
        self.config, self.on_complete = config, on_complete
        self.busy = False
        self._steps = []
        self._due = 0
        self.vertical.mid()
        self.horizontal.mid()

    @staticmethod
    def _move(servo, value):
        getattr(servo, {-1: "min", 0: "mid", 1: "max"}[value])()

    def start(self, direction, now):
        if self.busy:
            raise RuntimeError("Eine Sortierbewegung läuft bereits.")
        h, v = DIRECTIONS[direction]
        settle = self.config.servo_settle_seconds
        self._move(self.horizontal, h)
        self._steps = [(self.vertical, v, settle + self.config.drop_seconds),
                       (self.vertical, 0, settle), (self.horizontal, 0, settle), (None, 0, 0)]
        self._due = now + settle
        self.busy = True

    def update(self, now):
        if not self.busy or now < self._due:
            return
        servo, value, delay = self._steps.pop(0)
        if servo is None:
            self.busy = False
            self.on_complete()
            return
        self._move(servo, value)
        # A delayed UI tick must not compress physical servo settling times.
        self._due = now + delay

    def cancel(self):
        self.busy = False
        self._steps.clear()
        try:
            self.vertical.mid()
        finally:
            self.horizontal.mid()

    def close(self):
        try:
            self.cancel()
        finally:
            try:
                self.vertical.close()
            finally:
                self.horizontal.close()

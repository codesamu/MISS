"""SPI presentation with damage tracking and a latest-frame-only output worker."""

import queue
import threading


class DamageDisplay:
    """Retain ST7796 initialization, but transfer RGB565 changes only, exactly once."""

    def __init__(self, driver):
        self.driver = driver
        self.previous = None
        self.bytes_sent = 0
        self.windows_sent = 0

    @staticmethod
    def _rectangles(changed):
        # Merge equal horizontal tile runs vertically into nonoverlapping windows.
        rectangles, active = [], {}
        for row, values in enumerate(changed):
            spans, start = [], None
            for col, value in enumerate([*values, False]):
                if value and start is None:
                    start = col
                elif not value and start is not None:
                    spans.append((start, col))
                    start = None
            current = {}
            for span in spans:
                rect = active.pop(span, [span[0] * 32, row * 32, span[1] * 32, row * 32])
                rect[3] = (row + 1) * 32
                current[span] = rect
            rectangles.extend(active.values())
            active = current
        rectangles.extend(active.values())
        return rectangles

    def show_image(self, image):
        import numpy as np

        if image.size != (480, 320):
            raise ValueError("MISS-Display benötigt ein Bild mit 480 × 320 Pixeln.")
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint16)
        pixels = ((rgb[:, :, 0] & 0xF8) << 8) | ((rgb[:, :, 1] & 0xFC) << 3) | (rgb[:, :, 2] >> 3)
        if self.previous is None:
            rectangles = [(0, 0, 480, 320)]
            self.driver.command(0x36)
            self.driver.data(0xE8)
        else:
            changed = (pixels != self.previous).reshape(10, 32, 15, 32).any(axis=(1, 3))
            if not changed.any():
                return
            rectangles = self._rectangles(changed)
            if changed.sum() >= 112 or len(rectangles) > 16:
                rectangles = [(0, 0, 480, 320)]
        for x1, y1, x2, y2 in rectangles:
            self.driver.set_windows(x1, y1, x2 - 1, y2 - 1, 1)
            self.driver.digital_write(25, True)
            payload = pixels[y1:y2, x1:x2].astype(">u2").tobytes()
            spi = self.driver.SPI
            if hasattr(spi, "writebytes2"):
                spi.writebytes2(payload)
            else:
                for start in range(0, len(payload), 4096):
                    self.driver.spi_writebyte(list(payload[start:start + 4096]))
            self.bytes_sent += len(payload)
            self.windows_sent += 1
        self.previous = pixels

    def close(self):
        self.driver.close()


class LatestDisplay:
    """SPI may be slower than animation. Drop superseded frames instead of queuing."""

    def __init__(self, display):
        self.display = display
        self.error = None
        self._frames = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._write, name="miss-display", daemon=True)
        self._thread.start()

    def show_image(self, image):
        if self.error:
            raise RuntimeError("Displayübertragung fehlgeschlagen") from self.error
        if self._frames.full():
            try:
                self._frames.get_nowait()
            except queue.Empty:
                pass
        self._frames.put_nowait(image.copy())

    def _write(self):
        try:
            while not self._stop.is_set() or not self._frames.empty():
                try:
                    image = self._frames.get(timeout=0.05)
                except queue.Empty:
                    continue
                self.display.show_image(image)
        except Exception as error:
            self.error = error

    def close(self):
        self._stop.set()
        self._thread.join(timeout=2)
        if self._thread.is_alive():
            # Do not release GPIO/SPI while the writer is still using them.
            self._thread.join()
        self.display.close()

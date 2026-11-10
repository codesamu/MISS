import threading
import unittest

import numpy as np
from PIL import Image, ImageDraw

from miss_app.display import DamageDisplay, LatestDisplay


class Driver:
    def __init__(self):
        self.SPI = self
        self.frame = np.zeros((320, 480), dtype=np.uint16)
        self.windows = []
        self.payloads = []

    def command(self, value):
        pass

    def data(self, value):
        pass

    def digital_write(self, pin, value):
        pass

    def set_windows(self, x1, y1, x2, y2, horizontal):
        self.window = (x1, y1, x2, y2)
        self.windows.append(self.window)

    def writebytes2(self, payload):
        self.payloads.append(payload)
        x1, y1, x2, y2 = self.window
        self.frame[y1:y2 + 1, x1:x2 + 1] = np.frombuffer(payload, dtype=">u2").reshape(y2 - y1 + 1, x2 - x1 + 1)


class DisplayTests(unittest.TestCase):
    def test_full_frame_is_sent_once_with_inclusive_window_and_rgb565(self):
        driver = Driver()
        display = DamageDisplay(driver)
        display.show_image(Image.new("RGB", (480, 320), "red"))
        self.assertEqual(driver.windows, [(0, 0, 479, 319)])
        self.assertEqual(display.bytes_sent, 307200)
        self.assertEqual(driver.payloads[0][:2], b"\xf8\x00")
        self.assertTrue((driver.frame == 0xF800).all())

    def test_identical_quantized_frame_does_not_send_again(self):
        driver = Driver()
        display = DamageDisplay(driver)
        display.show_image(Image.new("RGB", (480, 320), (0, 0, 0)))
        display.show_image(Image.new("RGB", (480, 320), (1, 1, 1)))
        self.assertEqual(len(driver.payloads), 1)

    def test_separate_damage_regions_preserve_all_other_pixels(self):
        driver = Driver()
        display = DamageDisplay(driver)
        frame = Image.new("RGB", (480, 320), "black")
        display.show_image(frame)
        previous_bytes = display.bytes_sent
        draw = ImageDraw.Draw(frame)
        draw.rectangle((4, 4, 9, 9), fill="red")
        draw.rectangle((450, 290, 460, 310), fill="blue")
        display.show_image(frame)
        expected = np.zeros((320, 480), dtype=np.uint16)
        expected[4:10, 4:10] = 0xF800
        expected[290:311, 450:461] = 0x001F
        self.assertTrue(np.array_equal(driver.frame, expected))
        self.assertLess(display.bytes_sent - previous_bytes, 10000)

    def test_latest_frame_replaces_pending_frame_while_writer_is_busy(self):
        entered, release = threading.Event(), threading.Event()
        sent = []

        class Output:
            def show_image(self, image):
                sent.append(image.getpixel((0, 0)))
                if len(sent) == 1:
                    entered.set()
                    release.wait(1)

            def close(self):
                pass

        display = LatestDisplay(Output())
        try:
            display.show_image(Image.new("RGB", (480, 320), "red"))
            self.assertTrue(entered.wait(1))
            display.show_image(Image.new("RGB", (480, 320), "green"))
            display.show_image(Image.new("RGB", (480, 320), "blue"))
        finally:
            release.set()
            display.close()
        self.assertEqual(sent, [(255, 0, 0), (0, 0, 255)])


if __name__ == "__main__":
    unittest.main()

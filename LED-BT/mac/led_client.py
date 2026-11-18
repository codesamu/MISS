#!/usr/bin/env python3
"""Every command of the ESP32_LED strip, shown one after another on a Mac.

Run it and watch the strip:

    python3 Mac/led_client.py              # the whole show, ~20 s
    python3 Mac/led_client.py wave         # one step only
    python3 Mac/led_client.py onoff paint  # several steps, in that order

Steps: same-color, pattern, onoff, wave, breathe, fallback, stop

The BLE part (LedStrip) is the small reusable framework: connect once, then
call the command methods. The demo functions below show what each command does:

    strip.color(r, g, b)            all LEDs the same colour
    strip.set_led(i, r, g, b)       one LED, so first red and second white ...
    strip.on() / strip.off()        show / hide the last static picture
    strip.anim("WAVE", r, g, b, ms) animation with colour and speed
    strip.anim("BREATHE", ...)      the other animation
    strip.stop()                    stop the animation, static picture returns
    strip.send("ANIM WAVE")         raw command, missing values are reused

macOS notes
-----------
* The ESP32 is found by its advertised name "ESP32_LED". macOS shows a
  CoreBluetooth UUID instead of a MAC address, so pass --uuid=<uuid> only with
  a UUID printed by a scan on this Mac (see Mac/scan.py). It is not portable.
* macOS wants Bluetooth permission for the app you start Python from
  (Terminal, iTerm, IDE): System Settings -> Privacy & Security -> Bluetooth.
* The ESP32 serves one BLE connection at a time - close other clients first.

Python 3.9+, dependency: bleak.
"""

import asyncio
import sys

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    sys.exit("bleak is not installed. Run: pip install bleak")


# ---------------- BLE SETTINGS ----------------

DEVICE_NAME = "ESP32_LED"

SERVICE_UUID = "12345678-1234-1234-1234-123456789abc"
CHARACTERISTIC_UUID = "abcdefab-1234-1234-1234-abcdefabcdef"

SCAN_TIMEOUT = 10.0
WRITE_TIMEOUT = 5.0


# ---------------- LED STRIP ----------------


class LedStrip:
    """One connection to the ESP32; every method is one BLE write."""

    def __init__(self, name: str = DEVICE_NAME, uuid: str = ""):
        self.name = name
        self.uuid = uuid
        self.client = None

    # ---- connection ----

    async def connect(self):
        if self.uuid:
            # CoreBluetooth UUID, as printed by Mac/scan.py
            device = await BleakScanner.find_device_by_address(
                self.uuid, timeout=SCAN_TIMEOUT
            )
        else:
            device = await BleakScanner.find_device_by_filter(
                lambda d, adv: d.name == self.name or adv.local_name == self.name,
                timeout=SCAN_TIMEOUT,
            )

        if device is None:
            self._not_found()

        print(f"Found {device.name or self.name} ({device.address})")

        self.client = BleakClient(device, timeout=SCAN_TIMEOUT)

        try:
            await self.client.connect()
        except Exception as error:
            self._hint(error)
            raise

        if self.client.services.get_characteristic(CHARACTERISTIC_UUID) is None:
            await self.client.disconnect()
            self.client = None
            raise RuntimeError("Command characteristic not found - wrong firmware?")

        print("Connected")

    async def disconnect(self):
        client = self.client
        self.client = None

        if client is None:
            return

        try:
            if client.is_connected:
                await client.disconnect()
                print("Disconnected")
        except Exception as error:
            print(f"disconnect warning: {error}")

        # macOS closes the link asynchronously. Exiting right away can leave
        # the ESP32 waiting on a connection that is already gone, so it refuses
        # the next client. A short pause lets the disconnect finish.
        await asyncio.sleep(0.5)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *_):
        await self.disconnect()

    # ---- one write ----

    async def send(self, command: str):
        """Send one command, with response, so a failure is visible here."""

        if self.client is None or not self.client.is_connected:
            raise RuntimeError("not connected")

        await asyncio.wait_for(
            self.client.write_gatt_char(
                CHARACTERISTIC_UUID,
                command.encode("utf-8"),
                response=True,
            ),
            timeout=WRITE_TIMEOUT,
        )

        print(f"sent: {command}")

    # ---- commands ----

    async def on(self):
        await self.send("ON")

    async def off(self):
        await self.send("OFF")

    async def color(self, r: int, g: int, b: int):
        """One colour for the whole strip."""
        await self.send(f"COLOR {r} {g} {b}")

    async def set_led(self, index: int, r: int, g: int, b: int):
        """One colour for one LED (0-7)."""
        await self.send(f"SET {index} {r} {g} {b}")

    async def anim(self, effect: str, r: int, g: int, b: int, frame_ms: int = 40):
        """effect is WAVE or BREATHE; frame_ms is 10..2000."""
        await self.send(f"ANIM {effect.upper()} {r} {g} {b} {frame_ms}")

    async def stop(self):
        await self.send("STOP")

    # ---- macOS troubleshooting ----

    def _hint(self, error: Exception) -> None:
        text = str(error).lower()

        if "not authorized" in text or "permission" in text or "-17" in text:
            print()
            print("macOS refused Bluetooth access.")
            print("Allow the app you run Python from under")
            print("System Settings -> Privacy & Security -> Bluetooth, then retry.")
        elif "powered off" in text:
            print()
            print("Bluetooth is off. Turn it on in the macOS menu bar.")
        elif "busy" in text or "already" in text:
            print()
            print("Another client may already hold the ESP32 connection.")

    def _not_found(self) -> None:
        raise RuntimeError(
            f"{self.name} not found.\n"
            "Check: ESP32 powered on, in range, not connected to another client,\n"
            "and Bluetooth permission granted to your terminal app.\n"
            "To see what is visible, run: python3 Mac/scan.py"
        )


# ---------------- DEMO STEPS ----------------

# Colours used by the multi colour line: LED 0 red, LED 1 white, ...
PATTERN = [
    (255, 0, 0),      # 0 red
    (255, 255, 255),  # 1 white
    (0, 255, 0),      # 2 green
    (0, 0, 255),      # 3 blue
    (255, 255, 0),    # 4 yellow
    (0, 255, 255),    # 5 cyan
    (255, 0, 255),    # 6 magenta
    (255, 64, 0),     # 7 orange
]


async def step_same_color(strip: LedStrip):
    """COLOR - every LED the same colour."""

    print("all LEDs red")
    await strip.color(255, 0, 0)
    await asyncio.sleep(1.5)

    print("all LEDs light blue")
    await strip.color(0, 128, 255)
    await asyncio.sleep(1.5)


async def step_pattern(strip: LedStrip):
    """SET - a different colour for each LED."""

    print("one colour per LED: red, white, green, blue, yellow, cyan, magenta, orange")

    for index, (r, g, b) in enumerate(PATTERN):
        await strip.set_led(index, r, g, b)

    await asyncio.sleep(2.0)


async def step_onoff(strip: LedStrip):
    """OFF and ON - the static picture stays stored while the strip is off."""

    print("off - the saved picture disappears")
    await strip.off()
    await asyncio.sleep(1.5)

    print("on - the saved picture comes back")
    await strip.on()
    await asyncio.sleep(1.5)


async def step_wave(strip: LedStrip):
    """ANIM WAVE - a crest of light running along the strip."""

    print("wave in green, 40 ms per frame")
    await strip.anim("WAVE", 100, 255, 50, 10)
    await asyncio.sleep(3.0)


async def step_breathe(strip: LedStrip):
    """ANIM BREATHE - the whole strip fading up and down."""

    print("breathe in blue, 25 ms per frame")
    await strip.anim("BREATHE", 0, 0, 255, 5)
    await asyncio.sleep(3.0)


async def step_fallback(strip: LedStrip):
    """ANIM without values - the ESP32 reuses the last colour and speed."""

    print("ANIM WAVE without values keeps blue and 25 ms")
    await strip.send("ANIM WAVE")
    await asyncio.sleep(2.5)


async def step_stop(strip: LedStrip):
    """STOP - animation ends, the stored static picture comes back."""

    print("stop - the animation freezes and the multi colour line returns")
    await strip.stop()
    await asyncio.sleep(2.0)

    print("done, leaving the strip dark")
    await strip.off()


STEPS = {
    "same-color": step_same_color,
    "pattern": step_pattern,
    "onoff": step_onoff,
    "wave": step_wave,
    "breathe": step_breathe,
    "fallback": step_fallback,
    "stop": step_stop,
}

ORDER = list(STEPS)


# ---------------- RUN ----------------


async def show(strip: LedStrip, names):
    for name in names:
        print(f"\n--- {name} ---")
        await STEPS[name](strip)


async def run(names, uuid: str = ""):
    async with LedStrip(uuid=uuid) as strip:
        await show(strip, names)


def main():
    args = sys.argv[1:]

    uuid = next(
        (a.split("=", 1)[1] for a in args
         if a.startswith(("--uuid=", "--address="))),
        "",
    )

    names = [a.lower() for a in args if not a.startswith("-")] or ORDER

    unknown = [a for a in names if a not in STEPS]
    if unknown:
        sys.exit(f"Unknown step {unknown[0]!r}. Choose from: {', '.join(ORDER)}")

    asyncio.run(run(names, uuid))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as error:
        sys.exit(f"Error: {error}")


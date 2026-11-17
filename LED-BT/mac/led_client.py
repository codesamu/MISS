#!/usr/bin/env python3
"""Minimal LED control for the ESP32_LED strip, running on a Mac.

Same building block as RaspberryPi/led_client.py, adjusted for macOS / macOS
CoreBluetooth:

    async with LedStrip() as strip:              # connect / disconnect
        await strip.anim("WAVE", 0, 128, 255)    # start an effect
        await asyncio.sleep(4)                   # let it run
        await strip.color(255, 64, 0)            # one colour on the whole strip

Running this file plays exactly that: a blue wave for a few seconds, then the
whole strip in solid orange.

macOS notes
-----------
* The Bluetooth "address" macOS reports is a CoreBluetooth UUID, not the MAC
  address of the ESP32, and it differs per Mac. So the ESP32 is searched by its
  advertised name "ESP32_LED". Pass --uuid only to skip the scan (the UUID must
  be copied from a scan on this Mac, e.g. the one this script prints or
  RaspberryPi/test_esp32_commands.py --list).
* macOS asks once for Bluetooth permission. When the prompt appears, allow the
  app you start Python from - Terminal, iTerm, or the IDE. If you denied it,
  re-enable it under System Settings -> Privacy & Security -> Bluetooth.
  Without permission the scan silently finds nothing or bleak raises
  "not authorized".
* The ESP32 serves one BLE connection at a time. Close any other client (the Pi,
  phone app, nRF Connect) before running this.

Commands sent (see ESP32_LED.ino):
    ON | OFF | COLOR <r> <g> <b> | SET <led> <r> <g> <b>
    ANIM WAVE|BREATHE <r> <g> <b> <ms> | STOP

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
        device = None

        if self.uuid:
            # CoreBluetooth UUID or "UUID:CoreBluetooth" as printed by a scan
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
            raise RuntimeError("Command characteristic not found - wrong firmware?")

        print("Connected")

    async def disconnect(self):
        if self.client is not None and self.client.is_connected:
            await self.client.disconnect()
            print("Disconnected")

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
        await self.send(f"COLOR {r} {g} {b}")

    async def set_led(self, index: int, r: int, g: int, b: int):
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


# ---------------- DEMO ----------------


async def main():
    uuid = next((a.split("=", 1)[1] for a in sys.argv[1:]
                 if a.startswith(("--uuid=", "--address="))), "")

    async with LedStrip(uuid=uuid) as strip:

        print("wave for 4 s")
        await strip.anim("WAVE", 0, 128, 255, 40)
        await asyncio.sleep(4)

        print("solid orange")
        await strip.color(255, 64, 0)
        await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as error:
        sys.exit(f"Error: {error}")

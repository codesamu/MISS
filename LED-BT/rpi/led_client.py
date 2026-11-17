#!/usr/bin/env python3
"""Minimal LED control for the ESP32_LED strip (runs on the Raspberry Pi 4).

Small building block around the BLE characteristic of ESP32_LED.ino:

    async with LedStrip() as strip:              # connect / disconnect
        await strip.anim("WAVE", 0, 128, 255)    # start an effect
        await asyncio.sleep(4)                   # let it run
        await strip.color(255, 64, 0)            # one colour on the whole strip

Running this file plays exactly that: a blue wave for a few seconds, then the
whole strip in solid orange. Drop the LedStrip class into the sorting system
and call the same methods from there.

Commands sent (see ESP32_LED.ino):
    ON | OFF | COLOR <r> <g> <b> | SET <led> <r> <g> <b>
    ANIM WAVE|BREATHE <r> <g> <b> <ms> | STOP

Python 3.9+ (Raspberry Pi OS Bookworm), dependency: bleak.
"""

import asyncio

from bleak import BleakClient, BleakScanner

# ---------------- BLE SETTINGS ----------------

DEVICE_NAME = "ESP32_LED"

SERVICE_UUID = "12345678-1234-1234-1234-123456789abc"
CHARACTERISTIC_UUID = "abcdefab-1234-1234-1234-abcdefabcdef"

SCAN_TIMEOUT = 10.0
WRITE_TIMEOUT = 5.0


# ---------------- LED STRIP ----------------


class LedStrip:
    """One connection to the ESP32; every method is one BLE write."""

    def __init__(self, name: str = DEVICE_NAME, address: str = ""):
        self.name = name
        self.address = address
        self.client = None

    # ---- connection ----

    async def connect(self):
        device = None

        if self.address:
            device = await BleakScanner.find_device_by_address(
                self.address, timeout=SCAN_TIMEOUT
            )
        else:
            device = await BleakScanner.find_device_by_filter(
                lambda d, adv: d.name == self.name or adv.local_name == self.name,
                timeout=SCAN_TIMEOUT,
            )

        if device is None:
            raise RuntimeError(f"{self.name} not found - powered on and in range?")

        print(f"Found {device.name or self.name} ({device.address})")

        self.client = BleakClient(device, timeout=SCAN_TIMEOUT)
        await self.client.connect()

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


# ---------------- DEMO ----------------


async def main():
    async with LedStrip() as strip:

        print("wave for 4 s")
        await strip.anim("WAVE", 0, 128, 255, 40)
        await asyncio.sleep(4)

        print("solid orange")
        await strip.color(255, 64, 0)
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())

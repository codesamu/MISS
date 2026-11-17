#!/usr/bin/env python3
"""List the BLE devices macOS can see - use it to find the ESP32_LED UUID.

    python3 Mac/scan.py              # 10 s scan
    python3 Mac/scan.py 20           # longer scan

On macOS the address column is a CoreBluetooth UUID, not the ESP32's MAC
address. It is stable on one Mac but different on every other machine, so the
recommended way to connect is still the name ESP32_LED (see led_client.py).

An empty list usually means Bluetooth permission has not been granted to your
terminal app: System Settings -> Privacy & Security -> Bluetooth.
"""

import asyncio
import sys

try:
    from bleak import BleakScanner
except ImportError:
    sys.exit("bleak is not installed. Run: pip install bleak")


async def main() -> None:
    try:
        timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    except ValueError:
        sys.exit(f"Not a number of seconds: {sys.argv[1]!r}\nUsage: python3 Mac/scan.py [seconds]")

    print(f"Scanning for {timeout:.0f} s ...\n")

    devices = await BleakScanner.discover(timeout=timeout)

    if not devices:
        print("Nothing found.")
        print("Check Bluetooth permission for your terminal app and that")
        print("Bluetooth is switched on.")
        return

    for device in devices:
        print(f"  {device.address}  {device.name}")

    print()
    if any(d.name == "ESP32_LED" for d in devices):
        print("ESP32_LED is visible - run: python3 Mac/led_client.py")
    else:
        print("ESP32_LED not in the list: is it powered on and not connected")
        print("to another client?")


if __name__ == "__main__":
    asyncio.run(main())

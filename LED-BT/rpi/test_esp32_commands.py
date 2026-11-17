#!/usr/bin/env python3
"""Automatic command test for the ESP32_LED controller (runs on the Raspberry Pi 4).

The sketch ESP32_LED.ino accepts these commands on one writable BLE
characteristic:

    ON
    OFF
    COLOR <r> <g> <b>
    SET <led 0-7> <r> <g> <b>
    ANIM WAVE <r> <g> <b> <ms>
    ANIM BREATHE <r> <g> <b> <ms>
    STOP

This script sends every command form and the malformed variants, and reports
whether the ESP32 acknowledged each write. Commands are written with response,
which is the only write mode the characteristic offers, so a "PASS" means the
ESP32 received and processed the write without dropping the connection.

What a PASS does NOT prove: the sketch keeps no readable state. The read
characteristic always returns "Ready" from setup(), so nothing on the BLE side
tells us whether the LEDs actually changed colour. Every step therefore also
prints what you should see on the strip. Look at the LEDs while the script
runs, and watch the ESP32 serial monitor (115200 baud) for its log lines:
each received command is echoed there, along with the effect it applied.

Usage:
    source ~/ble-env/bin/activate
    python3 test_esp32_commands.py

    python3 test_esp32_commands.py --hold 1.0      # slower, easier to watch
    python3 test_esp32_commands.py --address AA:BB:CC:DD:EE:FF
    python3 test_esp32_commands.py --list          # only list visible devices

Exit code is 0 when every write was acknowledged, 1 otherwise.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from typing import Optional

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    sys.exit("bleak is not installed. Run: pip install bleak")

# ---------------- BLE SETTINGS ----------------

DEFAULT_DEVICE_NAME = "ESP32_LED"

# Same UUIDs as in ESP32_LED.ino - the contract between server and client.
SERVICE_UUID = "12345678-1234-1234-1234-123456789abc"
CHARACTERISTIC_UUID = "abcdefab-1234-1234-1234-abcdefabcdef"

CONNECT_TIMEOUT = 20.0
SCAN_TIMEOUT = 10.0
WRITE_TIMEOUT = 5.0


# ---------------- TEST STEPS ----------------


@dataclass
class Step:
    group: str
    command: str
    expect: str
    # Time to keep this state visible before the next command.
    hold: float = 0.8


def build_steps() -> list[Step]:
    """The full run, in an order where every step is visible on the strip."""

    return [
        # --- basic on/off ---
        Step("on/off", "ON",
             "all 8 LEDs on, last colour (white after a fresh boot)"),
        Step("on/off", "OFF",
             "strip goes dark"),
        Step("on/off", "on",
             "lowercase accepted: strip on again"),
        Step("on/off", "  off  ",
             "padded + lowercase accepted: strip dark"),

        # --- whole strip colour ---
        Step("color", "COLOR 255 0 0", "whole strip red"),
        Step("color", "COLOR 0 255 0", "whole strip green"),
        Step("color", "COLOR 0 0 255", "whole strip blue"),
        Step("color", "COLOR 255 255 255", "whole strip white"),

        # --- clamping: values outside 0..255 are constrained ---
        Step("clamp", "COLOR 300 -20 1000",
             "clamped to 255 0 255: whole strip magenta, no crash"),
        Step("clamp", "COLOR 10 20", "rejected: strip unchanged, ESP32 logs invalid colour"),

        # --- single LED ---
        Step("set", "COLOR 0 0 0", "strip dark"),
        Step("set", "SET 0 255 0 0", "only LED 0 red"),
        Step("set", "SET 7 0 0 255", "LED 0 red, LED 7 blue"),
        Step("set", "SET 3 255 255 0", "LED 3 additionally yellow"),
        Step("set", "SET 12 255 0 0",
             "index rejected (out of range): picture unchanged"),
        Step("set", "SET 1 255", "rejected: picture unchanged"),

        # --- animations ---
        Step("anim", "ANIM WAVE 255 0 0 40",
             "red crest runs along the strip", 2.0),
        Step("anim", "ANIM WAVE 0 255 0 200",
             "green crest runs much slower", 2.0),
        Step("anim", "ANIM BREATHE 0 0 255 25",
             "whole strip pulses blue", 2.0),
        Step("anim", "ANIM BREATHE 255 255 255 10",
             "whole strip pulses white quickly", 1.5),
        Step("anim", "ANIM WAVE",
             "no values given: falls back to white and the last frame time", 1.5),
        Step("anim", "ANIM SPARKLE 255 0 0 40",
             "unknown effect rejected: white breathing continues", 1.2),

        # --- stop the animation ---
        Step("stop", "STOP",
             "animation stops, previous static picture is shown again"),
        Step("stop", "COLOR 0 128 255", "static colour set, animation stays off"),

        # --- robustness: nothing here may disconnect or reboot the ESP32 ---
        Step("robust", "HELLO", "unknown command ignored, connection alive"),
        Step("robust", "", "empty write ignored, connection alive"),
        Step("robust", "COLOR", "invalid colour ignored, connection alive"),
        Step("robust", "SET 0 0 0 0", "LED 0 dark again"),
        Step("robust", "OFF", "strip dark, run finished"),
    ]


# ---------------- BLE HELPERS ----------------


async def find_device(name: str, timeout: float):
    """Find the ESP32 by advertised name (the address is not stable on all hosts)."""

    print(f"Searching for '{name}' ...")

    device = await BleakScanner.find_device_by_filter(
        lambda d, adv: d.name == name or adv.local_name == name,
        timeout=timeout,
    )

    return device


async def list_devices(timeout: float) -> None:
    print(f"Scanning for {timeout:.0f} s ...\n")

    for device in await BleakScanner.discover(timeout=timeout):
        print(f"  {device.address}  {device.name}")

    print("\nIf ESP32_LED is missing: is it powered on and not already connected")
    print("to another client (the sketch serves a single connection)?")


async def connect(address: str, name: str, timeout: float) -> BleakClient:
    """Connect and verify that the command characteristic really exists."""

    device = None

    if address:
        device = await BleakScanner.find_device_by_address(address, timeout=timeout)
        if device is None:
            sys.exit(f"Device {address} not found. Is it powered on and in range?")

    if device is None:
        device = await find_device(name, timeout)

    if device is None:
        sys.exit(
            f"'{name}' not found.\n"
            "ESP32 powered on and not connected to another client?"
        )

    print(f"Found: {device.name or '(no name)'} ({device.address})")

    client = BleakClient(device, timeout=CONNECT_TIMEOUT)
    await client.connect()

    print(f"Connected: {client.is_connected}")

    characteristic = client.services.get_characteristic(CHARACTERISTIC_UUID)

    if characteristic is None:
        await client.disconnect()
        sys.exit(
            f"Characteristic {CHARACTERISTIC_UUID} not found.\n"
            "Is the ESP32 running ESP32_LED.ino with these UUIDs?"
        )

    print(f"Characteristic properties: {characteristic.properties}")

    if "write" not in characteristic.properties and \
            "write-without-response" not in characteristic.properties:
        await client.disconnect()
        sys.exit("Characteristic is not writable - wrong firmware or wrong UUID?")

    return client


async def read_status(client: BleakClient) -> Optional[bytes]:
    """The sketch only ever reports its setup value, kept for a sanity check."""

    characteristic = client.services.get_characteristic(CHARACTERISTIC_UUID)

    if characteristic is None or "read" not in characteristic.properties:
        return None

    try:
        return await asyncio.wait_for(
            client.read_gatt_char(CHARACTERISTIC_UUID),
            timeout=WRITE_TIMEOUT,
        )
    except Exception:
        return None


async def send(client: BleakClient, command: str) -> None:
    """Write with response, exactly like the production client does."""

    await asyncio.wait_for(
        client.write_gatt_char(
            CHARACTERISTIC_UUID,
            command.encode("utf-8"),
            response=True,
        ),
        timeout=WRITE_TIMEOUT,
    )


# ---------------- TEST RUN ----------------


async def run(client: BleakClient, steps: list[Step], hold: float) -> int:
    results: list[tuple[Step, bool, str]] = []
    group = None

    for index, step in enumerate(steps, start=1):

        if step.group != group:
            group = step.group
            print()
            print(f"--- {group} ---")

        label = repr(step.command) if step.command else "(empty write)"
        print(f"[{index:02d}/{len(steps)}] {label}")

        try:
            await send(client, step.command)
            results.append((step, True, "acknowledged"))
            print(f"       ok - expect: {step.expect}")
        except asyncio.TimeoutError:
            results.append((step, False, "timeout"))
            print(f"       FAILED - no response within {WRITE_TIMEOUT:.0f} s")
        except Exception as error:
            results.append((step, False, f"{type(error).__name__}: {error}"))
            print(f"       FAILED - {type(error).__name__}: {error}")

            if not client.is_connected:
                print("       connection lost, stopping the run")
                break

        await asyncio.sleep(max(step.hold, hold))

    # ---------------- summary ----------------
    failed = [(step, detail) for step, ok, detail in results if not ok]

    print()
    print("=" * 60)
    print(f"{len(results) - len(failed)}/{len(results)} commands acknowledged")
    print("=" * 60)

    for step, detail in failed:
        print(f"FAILED  {step.command!r}: {detail}")

    if not failed:
        print("Every command form was accepted by the ESP32.")
        print("Now confirm the LED effects listed above actually happened;")
        print("write acknowledgement alone cannot prove the colours.")

    return 0 if not failed and len(results) == len(steps) else 1


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test every BLE command of the ESP32_LED controller.",
    )
    parser.add_argument("--name", default=DEFAULT_DEVICE_NAME,
                        help=f"advertised device name (default: {DEFAULT_DEVICE_NAME})")
    parser.add_argument("--address", default="",
                        help="connect to this Bluetooth address instead of scanning by name")
    parser.add_argument("--timeout", type=float, default=SCAN_TIMEOUT,
                        help=f"scan timeout in seconds (default: {SCAN_TIMEOUT:.0f})")
    parser.add_argument("--hold", type=float, default=0.0,
                        help="extra seconds to wait after each command")
    parser.add_argument("--list", action="store_true",
                        help="only list visible BLE devices, then exit")
    args = parser.parse_args()

    if args.list:
        await list_devices(args.timeout)
        return 0

    client = await connect(args.address, args.name, args.timeout)

    try:
        status = await read_status(client)
        if status:
            print(f"Status characteristic: {status.decode('utf-8', 'replace')!r}")

        print()
        print("Watch the LEDs and the ESP32 serial monitor (115200 baud).")

        return await run(client, build_steps(), args.hold)
    finally:
        if client.is_connected:
            await client.disconnect()
            print("Disconnected.")


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)

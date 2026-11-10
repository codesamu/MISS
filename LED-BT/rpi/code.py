import asyncio
from bleak import BleakScanner, BleakClient

DEVICE_NAME = "ESP32_LED"

CHARACTERISTIC_UUID = "abcdefab-1234-1234-1234-abcdefabcdef"


async def main():

    print("Searching for ESP32...")

    device = await BleakScanner.find_device_by_name(
        DEVICE_NAME,
        timeout=15
    )

    if device is None:
        print("ESP32 not found!")
        return

    print("ESP32 found:", device.address)

    async with BleakClient(device) as client:

        print("Connected to ESP32!")

        while True:

            print("\n--- LED CONTROL ---")
            print("1 - Turn ON")
            print("2 - Turn OFF")
            print("3 - Red")
            print("4 - Green")
            print("5 - Blue")
            print("6 - Custom RGB")
            print("0 - Exit")

            choice = input("Choose: ")

            if choice == "1":
                command = "ON"

            elif choice == "2":
                command = "OFF"

            elif choice == "3":
                command = "COLOR 255 0 0"

            elif choice == "4":
                command = "COLOR 0 255 0"

            elif choice == "5":
                command = "COLOR 0 0 255"

            elif choice == "6":

                r = int(input("Red (0-255): "))
                g = int(input("Green (0-255): "))
                b = int(input("Blue (0-255): "))

                command = f"COLOR {r} {g} {b}"

            elif choice == "0":
                print("Exiting...")
                break

            else:
                print("Invalid choice!")
                continue

            await client.write_gatt_char(
                CHARACTERISTIC_UUID,
                command.encode("utf-8"),
                response=True
            )

            print("Sent:", command)


asyncio.run(main())

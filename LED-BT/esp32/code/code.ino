
#include <FastLED.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>

// ---------------- LED SETTINGS ----------------

#define LED_PIN 14
#define NUM_LEDS 8
#define LED_TYPE WS2812B
#define COLOR_ORDER GRB

CRGB leds[NUM_LEDS];

bool ledState = false;
CRGB currentColor = CRGB::White;

// ---------------- BLE SETTINGS ----------------

#define DEVICE_NAME "ESP32_LED"

#define SERVICE_UUID \
"12345678-1234-1234-1234-123456789abc"

#define CHARACTERISTIC_UUID \
"abcdefab-1234-1234-1234-abcdefabcdef"

// ---------------- LED CONTROL ----------------

void updateLEDs() {

  if (ledState) {
    fill_solid(leds, NUM_LEDS, currentColor);
  } else {
    fill_solid(leds, NUM_LEDS, CRGB::Black);
  }

  FastLED.show();
}

// ---------------- BLE COMMANDS ----------------

class CommandCallbacks : public BLECharacteristicCallbacks {

  void onWrite(BLECharacteristic *characteristic) override {

    // Read incoming BLE command
    String command = characteristic->getValue();

    command.trim();
    command.toUpperCase();

    Serial.print("Received command: ");
    Serial.println(command);

    // TURN ON
    if (command == "ON") {

      ledState = true;
      updateLEDs();

      Serial.println("LEDs ON");
    }

    // TURN OFF
    else if (command == "OFF") {

      ledState = false;
      updateLEDs();

      Serial.println("LEDs OFF");
    }

    // CHANGE COLOR
    else if (command.startsWith("COLOR")) {

      int r, g, b;

      if (sscanf(command.c_str(),
                 "COLOR %d %d %d",
                 &r, &g, &b) == 3) {

        // Keep values between 0 and 255
        r = constrain(r, 0, 255);
        g = constrain(g, 0, 255);
        b = constrain(b, 0, 255);

        currentColor = CRGB(r, g, b);

        ledState = true;
        updateLEDs();

        Serial.printf(
          "New RGB: %d, %d, %d\n",
          r, g, b
        );

      } else {

        Serial.println("Invalid color command!");

      }
    }

    else {

      Serial.println("Unknown command!");

    }
  }
};

// ---------------- SETUP ----------------

void setup() {

  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("Starting ESP32 LED controller...");

  // Initialize FastLED
  FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(
    leds, NUM_LEDS
  );

  FastLED.setBrightness(50);

  updateLEDs();

  Serial.println("FastLED initialized!");

  // Initialize Bluetooth
  BLEDevice::init(DEVICE_NAME);

  BLEServer *server = BLEDevice::createServer();

  BLEService *service =
    server->createService(SERVICE_UUID);

  BLECharacteristic *characteristic =
    service->createCharacteristic(
      CHARACTERISTIC_UUID,
      BLECharacteristic::PROPERTY_READ |
      BLECharacteristic::PROPERTY_WRITE
    );

  characteristic->setCallbacks(new CommandCallbacks());

  characteristic->setValue("Ready");

  // Start BLE service
  service->start();

  // Start Bluetooth advertising
  BLEAdvertising *advertising =
    BLEDevice::getAdvertising();

  advertising->addServiceUUID(SERVICE_UUID);
  advertising->setScanResponse(true);

  BLEDevice::startAdvertising();

  Serial.println("BLE initialized!");
  Serial.println("Device name: ESP32_LED");
  Serial.println("Waiting for Raspberry Pi...");
}

// ---------------- LOOP ----------------

void loop() {

  delay(100);

}

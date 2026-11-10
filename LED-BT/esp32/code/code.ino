#include <FastLED.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// LED configuration
#define LED_PIN 14
#define NUM_LEDS 8
#define LED_TYPE WS2812B
#define COLOR_ORDER GRB

CRGB leds[NUM_LEDS];

// BLE configuration
#define DEVICE_NAME "ESP32_LED"

#define SERVICE_UUID        "12345678-1234-1234-1234-123456789abc"
#define CHARACTERISTIC_UUID "abcdefab-1234-1234-1234-abcdefabcdef"

// LED state
bool ledState = false;
CRGB currentColor = CRGB::White;

// Update LEDs
void updateLEDs() {
  if (ledState) {
    fill_solid(leds, NUM_LEDS, currentColor);
  } else {
    fill_solid(leds, NUM_LEDS, CRGB::Black);
  }

  FastLED.show();
}

// BLE command handler
class CommandCallbacks : public BLECharacteristicCallbacks {

  void onWrite(BLECharacteristic *pCharacteristic) {

    String command = pCharacteristic->getValue().c_str();

    command.trim();
    command.toUpperCase();

    Serial.print("Received: ");
    Serial.println(command);

    if (command == "ON") {

      ledState = true;
      updateLEDs();

    }

    else if (command == "OFF") {

      ledState = false;
      updateLEDs();

    }

    else if (command.startsWith("COLOR")) {

      int r, g, b;

      if (sscanf(command.c_str(), "COLOR %d %d %d", &r, &g, &b) == 3) {

        r = constrain(r, 0, 255);
        g = constrain(g, 0, 255);
        b = constrain(b, 0, 255);

        currentColor = CRGB(r, g, b);

        ledState = true;
        updateLEDs();

        Serial.println("Color changed!");

      }
    }
  }
};

void setup() {

  Serial.begin(115200);

  // Initialize LEDs
  FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(50);

  ledState = false;
  updateLEDs();

  // Initialize Bluetooth
  BLEDevice::init(DEVICE_NAME);

  BLEServer *pServer = BLEDevice::createServer();

  BLEService *pService = pServer->createService(SERVICE_UUID);

  BLECharacteristic *pCharacteristic =
    pService->createCharacteristic(
      CHARACTERISTIC_UUID,
      BLECharacteristic::PROPERTY_READ |
      BLECharacteristic::PROPERTY_WRITE
    );

  pCharacteristic->setCallbacks(new CommandCallbacks());

  pCharacteristic->setValue("Ready");

  pService->start();

  // Start advertising
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();

  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);

  BLEDevice::startAdvertising();

  Serial.println("ESP32 BLE is ready!");
  Serial.println("Waiting for Raspberry Pi...");
}

void loop() {
  delay(100);
}

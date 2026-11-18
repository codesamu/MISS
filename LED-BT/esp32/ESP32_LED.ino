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

// Static picture: one color per LED, drawn when no animation is running.
CRGB baseColors[NUM_LEDS];

bool ledState = false;

// Color the animations draw with.
CRGB currentColor = CRGB::White;

// ---------------- ANIMATION SETTINGS ----------------

enum AnimationMode {
  ANIM_NONE,
  ANIM_WAVE,
  ANIM_BREATHE
};

AnimationMode animation = ANIM_NONE;

uint8_t animPhase = 0;         // 0..255, moves the effects along
uint16_t animDelayMs = 40;     // time between two frames
unsigned long lastFrame = 0;   // millis() of the last drawn frame

// ---------------- BLE SETTINGS ----------------

#define DEVICE_NAME "ESP32_LED"

#define SERVICE_UUID \
"12345678-1234-1234-1234-123456789abc"

#define CHARACTERISTIC_UUID \
"abcdefab-1234-1234-1234-abcdefabcdef"

// ---------------- LED CONTROL ----------------

void updateLEDs() {

  if (ledState) {
    for (int i = 0; i < NUM_LEDS; i++) {
      leds[i] = baseColors[i];
    }
  } else {
    fill_solid(leds, NUM_LEDS, CRGB::Black);
  }

  FastLED.show();
}

// One static color for the whole strip
void setAllLEDs(CRGB color) {

  fill_solid(baseColors, NUM_LEDS, color);
  currentColor = color;

  animation = ANIM_NONE;
  ledState = true;

  updateLEDs();
}

// One static color for a single LED
void setOneLED(int index, CRGB color) {

  if (index < 0 || index >= NUM_LEDS) {
    Serial.println("LED index out of range (0-7)!");
    return;
  }

  baseColors[index] = color;
  currentColor = color;

  animation = ANIM_NONE;
  ledState = true;

  updateLEDs();
}

// ---------------- ANIMATIONS ----------------

// One call decides everything: effect, color and speed.
void startAnimation(String name, CRGB color, uint16_t frameMs) {

  name.trim();

  if (name == "WAVE") {
    animation = ANIM_WAVE;
  } else if (name == "BREATHE") {
    animation = ANIM_BREATHE;
  } else {
    Serial.println("Unknown animation! Use WAVE or BREATHE");
    return;
  }

  currentColor = color;
  animDelayMs = constrain(frameMs, 10, 2000);

  ledState = true;
  animPhase = 0;
  lastFrame = 0;   // draw the first frame right away

  Serial.printf("Animation %s, RGB %d %d %d, frame time %d ms\n",
                name.c_str(), color.r, color.g, color.b, animDelayMs);
}

// Draws exactly one frame, so BLE keeps working in between.
void renderAnimation() {

  unsigned long now = millis();

  // Not yet time for the next frame
  if (now - lastFrame < animDelayMs) {
    return;
  }

  lastFrame = now;
  animPhase += 4;

  switch (animation) {

    // A crest of light runs along the strip in the current color
    case ANIM_WAVE: {
      for (int i = 0; i < NUM_LEDS; i++) {
        uint8_t offset = (uint8_t)(animPhase + (i * 256) / NUM_LEDS);
        uint8_t sine = sin8(offset);
        uint8_t level = scale8(sine, sine);   // sharpens the crest

        leds[i] = currentColor;
        leds[i].nscale8_video(level);
      }
      break;
    }

    // Whole strip fades up and down in the current color
    case ANIM_BREATHE: {
      uint8_t level = sin8(animPhase);

      for (int i = 0; i < NUM_LEDS; i++) {
        leds[i] = currentColor;
        leds[i].nscale8_video(level);
      }
      break;
    }

    default:
      return;
  }

  FastLED.show();
}

// ---------------- BLE CONNECTION ----------------

// A connection and advertising exclude each other. The stack stops advertising
// when a client connects, and it does NOT start again after that client leaves
// - without the restart below the board is invisible until it is reset.
//
// Both calls happen here, in the Bluetooth task that owns them, and nowhere
// else: starting advertising from loop() races with the stack and makes the
// next connection fail.
//
// Nothing is printed in these callbacks: Serial output from the Bluetooth task
// can block it and drop the link. loop() does the printing.
volatile bool clientConnected = false;

bool reportedConnected = false;   // last state printed by loop()

class ServerCallbacks : public BLEServerCallbacks {

  void onConnect(BLEServer *server) override {

    clientConnected = true;

    BLEDevice::stopAdvertising();
  }

  void onDisconnect(BLEServer *server) override {

    clientConnected = false;

    BLEDevice::startAdvertising();   // visible again for the next client
  }
};

// ---------------- BLE COMMANDS ----------------

class CommandCallbacks : public BLECharacteristicCallbacks {

  void onWrite(BLECharacteristic *characteristic) override {

    // Read incoming BLE command
    String command(characteristic->getValue().c_str());

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
      animation = ANIM_NONE;
      updateLEDs();

      Serial.println("LEDs OFF");
    }

    // CHANGE COLOR OF THE WHOLE STRIP
    else if (command.startsWith("COLOR")) {

      int r, g, b;

      if (sscanf(command.c_str(),
                 "COLOR %d %d %d",
                 &r, &g, &b) == 3) {

        // Keep values between 0 and 255
        r = constrain(r, 0, 255);
        g = constrain(g, 0, 255);
        b = constrain(b, 0, 255);

        setAllLEDs(CRGB(r, g, b));

        Serial.printf(
          "New RGB: %d, %d, %d\n",
          r, g, b
        );

      } else {

        Serial.println("Invalid color command!");

      }
    }

    // CHANGE COLOR OF ONE LED: SET <index> <r> <g> <b>
    else if (command.startsWith("SET")) {

      int index, r, g, b;

      if (sscanf(command.c_str(),
                 "SET %d %d %d %d",
                 &index, &r, &g, &b) == 4) {

        r = constrain(r, 0, 255);
        g = constrain(g, 0, 255);
        b = constrain(b, 0, 255);

        setOneLED(index, CRGB(r, g, b));

        Serial.printf(
          "LED %d -> RGB: %d, %d, %d\n",
          index, r, g, b
        );

      } else {

        Serial.println("Invalid SET command! Use: SET 0 255 0 0");

      }
    }

    // START AN ANIMATION WITH COLOR AND SPEED IN ONE LINE
    // ANIM WAVE 255 0 0 40
    // ANIM BREATHE 0 0 255 25
    else if (command.startsWith("ANIM")) {

      char name[16] = "";

      // Missing values fall back to the last color / speed
      int r = currentColor.r;
      int g = currentColor.g;
      int b = currentColor.b;
      int ms = animDelayMs;

      if (sscanf(command.c_str(),
                 "ANIM %15s %d %d %d %d",
                 name, &r, &g, &b, &ms) >= 1) {

        r = constrain(r, 0, 255);
        g = constrain(g, 0, 255);
        b = constrain(b, 0, 255);
        ms = constrain(ms, 10, 2000);

        startAnimation(String(name), CRGB(r, g, b), (uint16_t)ms);

      } else {

        Serial.println("Usage: ANIM WAVE 255 0 0 40");

      }
    }

    // STOP THE ANIMATION AND SHOW THE STATIC PICTURE
    else if (command == "STOP") {

      animation = ANIM_NONE;
      updateLEDs();

      Serial.println("Animation stopped");
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

  fill_solid(baseColors, NUM_LEDS, CRGB::Black);
  updateLEDs();

  Serial.println("FastLED initialized!");

  // Initialize Bluetooth
  BLEDevice::init(DEVICE_NAME);

  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new ServerCallbacks());

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

  // Connection parameters macOS and iOS accept without dropping the link
  advertising->setMinPreferred(0x06);
  advertising->setMaxPreferred(0x12);

  BLEDevice::startAdvertising();

  Serial.println("BLE initialized!");
  Serial.println("Device name: ESP32_LED");
  Serial.println("Commands:");
  Serial.println("  ON / OFF");
  Serial.println("  COLOR <r> <g> <b>");
  Serial.println("  SET <led 0-7> <r> <g> <b>");
  Serial.println("  ANIM WAVE <r> <g> <b> <ms>");
  Serial.println("  ANIM BREATHE <r> <g> <b> <ms>");
  Serial.println("  STOP");
  Serial.println("Waiting for Raspberry Pi...");
}

// ---------------- LOOP ----------------

void loop() {

  // Connection log. Printing from loop() keeps the Bluetooth task free.
  if (clientConnected != reportedConnected) {

    reportedConnected = clientConnected;

    Serial.println(reportedConnected ? "Client connected - ready for commands"
                                     : "Client disconnected - advertising again");
  }

  // Animations are drawn frame by frame here instead of in the
  // BLE callback, so a blocking effect can never stall Bluetooth.
  if (ledState && animation != ANIM_NONE) {
    renderAnimation();
  }

  delay(5);
}


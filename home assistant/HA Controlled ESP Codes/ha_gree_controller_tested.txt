

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#include <IRremoteESP8266.h>
#include <IRsend.h>
#include <ir_Gree.h>

// ─────────────────────────────────────────────
// Configuration
// ─────────────────────────────────────────────
#define IR_LED_PIN       4       // Change if needed (GPIO23 also good)
#define POLL_INTERVAL_MS 5000
#define SEND_REPEATS     3
#define SEND_DELAY_MS    100

// WiFi & Home Assistant (same as Daikin)
const char* ssid     = "GuestAccess";
const char* password = "MRSPAK@ISB";

const char* ha_host  = "10.255.0.145";
const int   ha_port  = 8123;
const char* ha_entry = "01KE8XV949Y8CRTN1V67237V5G";
const char* ha_key   = "abcd";

// ─────────────────────────────────────────────
// Globals
// ─────────────────────────────────────────────
IRsend irsend(IR_LED_PIN);
IRGreeAC ac(IR_LED_PIN);

unsigned long lastPoll = 0;
bool shouldSend = false;

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n=== Gree AC Home Assistant Controller (ESP32) ===");
  Serial.println("Starting...");

  // WiFi connection
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi: ");
  Serial.print(ssid);
  Serial.print(" ...");

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi CONNECTED!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal strength (RSSI): ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("\nWiFi connection FAILED!");
    Serial.println("Will retry in loop...");
  }

  // Initialize IR & Gree AC
  irsend.begin();
  ac.begin();

  // Default state (optional - you can remove or change)
  ac.on();
  ac.setMode(kGreeCool);
  ac.setTemp(22);
  ac.setFan(kGreeFanMed);
  ac.setSwingVertical(true, kGreeSwingAuto);
  ac.setTurbo(false);
  ac.setLight(true);
  ac.setXFan(false);
  ac.setSleep(false);

  Serial.println("Gree AC initialized - sending initial state...");
  sendCommand();

  Serial.println("Ready. Polling Home Assistant every 5 seconds.\n");
}

void loop() {
  // Check WiFi status periodically
  static unsigned long lastStatusPrint = 0;
  if (millis() - lastStatusPrint > 30000) {  // every 30 seconds
    lastStatusPrint = millis();
    printWifiStatus();
  }

  // Poll HA
  unsigned long now = millis();
  if (now - lastPoll >= POLL_INTERVAL_MS) {
    lastPoll = now;
    if (WiFi.status() == WL_CONNECTED) {
      checkHACommands();
    } else {
      Serial.println("[WARNING] WiFi disconnected - skipping HA poll");
    }
  }

  // Send if HA commands changed something
  if (shouldSend) {
    Serial.println("State changed by HA → sending new command to AC");
    sendCommand();
    shouldSend = false;
  }

  delay(50);
}

// Print WiFi status
void printWifiStatus() {
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("[STATUS] WiFi OK | IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("[STATUS] WiFi DISCONNECTED!");
  }
}

// Send current AC state (your original style)
void sendCommand() {
  Serial.println("Sending Gree AC command...");
  for (int i = 0; i < SEND_REPEATS; i++) {
    ac.send();
    delay(SEND_DELAY_MS);
  }
  Serial.println("→ Command sent successfully\n");
}

// Poll Home Assistant and process commands
void checkHACommands() {
  HTTPClient http;
  WiFiClient client;

  String url = "http://";
  url += ha_host;
  url += ":";
  url += String(ha_port);
  url += "/api/my_inverter/";
  url += ha_entry;
  url += "/commands?api_key=";
  url += ha_key;

  Serial.print("Polling HA → ");
  Serial.println(url);

  http.begin(client, url);
  http.addHeader("X-API-Key", ha_key);

  int httpCode = http.GET();

  if (httpCode > 0) {
    Serial.print("HTTP Response code: ");
    Serial.println(httpCode);

    if (httpCode == HTTP_CODE_OK) {
      String payload = http.getString();
      // Serial.println("Raw response: " + payload);  // uncomment for full debug

      DynamicJsonDocument doc(1024);
      DeserializationError error = deserializeJson(doc, payload);

      if (error) {
        Serial.print("JSON parse error: ");
        Serial.println(error.c_str());
      } else {
        JsonArray commands = doc["commands"];
        bool anyChange = false;

        if (commands.size() == 0) {
          Serial.println("No new commands from HA");
        }

        for (JsonVariant cmdVar : commands) {
          String cmd = cmdVar.as<String>();

          // ─────────────── IMPORTANT: Print every command ───────────────
          Serial.println("HA Command received: " + cmd);

          // Process commands (same format as Daikin)
          if (cmd.startsWith("SET_TEMP_")) {
            int temp = cmd.substring(9).toInt();
            if (temp >= 16 && temp <= 30) {
              ac.setTemp(temp);
              anyChange = true;
              Serial.printf("  → Set temperature to %d°C\n", temp);
            } else {
              Serial.println("  → Invalid temperature value");
            }
          }
          else if (cmd.startsWith("SET_MODE_")) {
            String mode = cmd.substring(9);
            mode.toLowerCase();
            Serial.print("  → Set mode: " + mode);

            if (mode == "off") {
              ac.off();
              Serial.println(" (power OFF)");
            } else {
              ac.on();
              if (mode == "cool")      ac.setMode(kGreeCool);
              else if (mode == "heat") ac.setMode(kGreeHeat);
              else if (mode == "auto") ac.setMode(kGreeAuto);
              else if (mode == "dry")  ac.setMode(kGreeDry);
              else if (mode == "fan")  ac.setMode(kGreeFan);
              else {
                Serial.println(" → invalid mode");
                continue;
              }
              Serial.println(" (power ON)");
            }
            anyChange = true;
          }
          else if (cmd.startsWith("SET_FAN_")) {
            int fan = cmd.substring(8).toInt();
            Serial.print("  → Set fan speed: " + String(fan));
            switch (fan) {
              case 0: ac.setFan(kGreeFanAuto); Serial.println(" (Auto)"); break;
              case 1: ac.setFan(kGreeFanMin);  Serial.println(" (Low)");  break;
              case 2: ac.setFan(kGreeFanMed);  Serial.println(" (Medium)"); break;
              case 3: ac.setFan(kGreeFanMax);  Serial.println(" (High)"); break;
              default: Serial.println(" → invalid"); continue;
            }
            anyChange = true;
          }
          else if (cmd == "SWITCH_ON") {
            ac.on();
            Serial.println("  → Power ON");
            anyChange = true;
          }
          else if (cmd == "SWITCH_OFF") {
            ac.off();
            Serial.println("  → Power OFF");
            anyChange = true;
          }
          else {
            Serial.println("  → Unknown/ignored command");
          }
        }

        if (anyChange) {
          shouldSend = true;
          Serial.println("State changed - will send new IR command soon");
        }
      }
    }
  } else {
    Serial.print("HTTP GET failed! Error: ");
    Serial.println(http.errorToString(httpCode));
  }

  http.end();
  Serial.println("───────────────────────────────\n");
}
/*
  AgriN Twin — Sensor Pod Firmware (ESP32)
  =========================================
  Reads soil moisture, soil temperature, air temperature/humidity, and
  soil conductivity (nutrient/salinity proxy), then POSTs a JSON reading
  to the AgriN Twin backend every SEND_INTERVAL_MS. Deep-sleeps between
  readings to run for months on a small solar/battery setup — critical
  for smallholder deployments with no reliable grid power.

  BILL OF MATERIALS (~₹500 / ~$6 target cost per pod):
    - ESP32-WROOM-32 dev board
    - Capacitive soil moisture sensor (v1.2)
    - DS18B20 waterproof soil temperature probe
    - DHT22 air temperature/humidity sensor
    - Two-probe soil conductivity sensor (or a simple two-nail probe +
      voltage-divider circuit for a low-cost conductivity proxy)
    - 18650 Li-ion cell + TP4056 charge module + small solar panel (optional)

  WIRING (adjust pins to your board):
    Soil moisture (analog)   -> GPIO34
    Soil conductivity (analog)-> GPIO35
    DS18B20 (OneWire)        -> GPIO4
    DHT22 (digital)          -> GPIO14
    Battery voltage divider  -> GPIO32

  Requires libraries: WiFi.h, HTTPClient.h, ArduinoJson, DHT sensor library,
  OneWire, DallasTemperature.
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ---------- CONFIGURE PER DEPLOYMENT ----------
const char* WIFI_SSID       = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD   = "YOUR_WIFI_PASSWORD";
const char* API_BASE_URL    = "https://your-agrintwin-deployment.example.com/api/v1";
const char* PLOT_ID         = "REPLACE_WITH_PLOT_UUID_FROM_DASHBOARD";
const char* POD_API_KEY     = "REPLACE_WITH_IOT_INGEST_API_KEY";

const unsigned long SEND_INTERVAL_MS = 15UL * 60UL * 1000UL;  // 15 minutes
const uint64_t DEEP_SLEEP_US = 15ULL * 60ULL * 1000000ULL;    // 15 minutes

// ---------- PIN CONFIG ----------
#define SOIL_MOISTURE_PIN   34
#define SOIL_CONDUCTIVITY_PIN 35
#define ONE_WIRE_BUS         4
#define DHT_PIN              14
#define DHT_TYPE              DHT22
#define BATTERY_PIN          32

DHT dht(DHT_PIN, DHT_TYPE);
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature soilTempSensor(&oneWire);

// Calibration constants — determine empirically per sensor batch by
// testing in dry air (0%) and in a cup of water (100%).
const int SOIL_MOISTURE_DRY_RAW = 3000;
const int SOIL_MOISTURE_WET_RAW = 1200;

float readSoilMoisturePercent() {
  int raw = analogRead(SOIL_MOISTURE_PIN);
  float pct = (float)(SOIL_MOISTURE_DRY_RAW - raw) / (SOIL_MOISTURE_DRY_RAW - SOIL_MOISTURE_WET_RAW) * 100.0;
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  return pct;
}

float readSoilConductivity() {
  int raw = analogRead(SOIL_CONDUCTIVITY_PIN);
  // Simple linear proxy in microsiemens/cm — replace with a proper
  // calibration curve for production nutrient estimation.
  return raw * 0.6;
}

float readBatteryVoltage() {
  int raw = analogRead(BATTERY_PIN);
  // Assumes a 2:1 voltage divider (100k/100k) into the ADC (3.3V ref, 12-bit)
  return (raw / 4095.0) * 3.3 * 2.0;
}

bool connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(500);
  }
  return WiFi.status() == WL_CONNECTED;
}

void sendReading(float soilMoisture, float soilTemp, float airTemp, float airHumidity, float conductivity, float battery) {
  HTTPClient http;
  String url = String(API_BASE_URL) + "/sensor-readings";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Pod-Api-Key", POD_API_KEY);

  StaticJsonDocument<512> doc;
  doc["plot_id"] = PLOT_ID;
  doc["soil_moisture_pct"] = soilMoisture;
  doc["soil_temp_c"] = soilTemp;
  doc["air_temp_c"] = airTemp;
  doc["air_humidity_pct"] = airHumidity;
  doc["soil_conductivity_us_cm"] = conductivity;
  doc["battery_voltage"] = battery;

  String payload;
  serializeJson(doc, payload);

  int httpCode = http.POST(payload);
  Serial.printf("POST /sensor-readings -> HTTP %d\n", httpCode);
  if (httpCode > 0) {
    Serial.println(http.getString());
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(200);

  dht.begin();
  soilTempSensor.begin();
  analogReadResolution(12);

  float soilMoisture = readSoilMoisturePercent();
  soilTempSensor.requestTemperatures();
  float soilTemp = soilTempSensor.getTempCByIndex(0);
  float airTemp = dht.readTemperature();
  float airHumidity = dht.readHumidity();
  float conductivity = readSoilConductivity();
  float battery = readBatteryVoltage();

  if (isnan(airTemp) || isnan(airHumidity)) {
    Serial.println("DHT22 read failed — using last-known/default values.");
    airTemp = 28.0;
    airHumidity = 65.0;
  }

  if (connectWiFi()) {
    sendReading(soilMoisture, soilTemp, airTemp, airHumidity, conductivity, battery);
  } else {
    Serial.println("WiFi connect failed — reading discarded this cycle. "
                    "Production: buffer to SPIFFS and retry next wake.");
  }

  WiFi.disconnect(true);
  Serial.println("Entering deep sleep...");
  esp_sleep_enable_timer_wakeup(DEEP_SLEEP_US);
  esp_deep_sleep_start();
}

void loop() {
  // unused — device wakes, sends, and deep-sleeps via setup()
}

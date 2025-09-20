#include <Arduino.h>

#define METER1 5   // PWM-capable pins
#define METER2 6
#define METER3 9

// Metric store
const int MAX_METRICS = 20;
String metricNames[MAX_METRICS];
int metricValues[MAX_METRICS];
int metricCount = 0;

// Mapping (store index of the metric for each meter, -1 = unmapped)
int mapM1 = -1;
int mapM2 = -1;
int mapM3 = -1;

String inputLine = "";

void setup() {
  Serial.begin(115200);
  pinMode(METER1, OUTPUT);
  pinMode(METER2, OUTPUT);
  pinMode(METER3, OUTPUT);

  Serial.println("Arduino ready. Use 'map:METERx=metric.name' to assign meters.");
}

void loop() {
  // Read incoming serial lines
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      processLine(inputLine);
      inputLine = "";
    } else if (c != '\r') {
      inputLine += c;
    }
  }

  // Continuously output mapped values
  if (mapM1 >= 0) analogWrite(METER1, metricValues[mapM1]);
  if (mapM2 >= 0) analogWrite(METER2, metricValues[mapM2]);
  if (mapM3 >= 0) analogWrite(METER3, metricValues[mapM3]);
}

void processLine(const String& line) {
  if (line.startsWith("map:")) {
    handleMapping(line.substring(4));
    return;
  }

  int colonIndex = line.indexOf(':');
  if (colonIndex == -1) {
    Serial.print("Invalid metric line: ");
    Serial.println(line);
    return;
  }

  String metric = line.substring(0, colonIndex);
  String valueStr = line.substring(colonIndex + 1);
  int value = valueStr.toInt();
  value = constrain(value, 0, 255);

  // Look up or add metric
  int idx = findOrAddMetric(metric);
  metricValues[idx] = value;

  setDefaultMeter(metric);
  Serial.print("Updated metric ");
  Serial.print(metric);
  Serial.print(" = ");
  Serial.println(value);
}

/*
If an unutilized meter exists, set it. 
*/
int setDefaultMeter(String metric) {
  if (mapM1 == -1) {
    mapM1 = findOrAddMetric(metric);
    return 1;
  } else if (mapM2 == -1) {
    mapM2 = findOrAddMetric(metric);
    return 1;
  } else if (mapM3 == -1) {
    mapM3 = findOrAddMetric(metric);
    return 1;
  }
  return 0;
}

int findOrAddMetric(const String& name) {
  for (int i = 0; i < metricCount; i++) {
    if (metricNames[i] == name) return i;
  }
  if (metricCount < MAX_METRICS) {
    metricNames[metricCount] = name;
    metricValues[metricCount] = 0;
    return metricCount++;
  }
  Serial.println("Metric store full!");
  return 0; // fallback
}

void handleMapping(const String& cmd) {
  // Format: METERx=metric.name
  int eqIdx = cmd.indexOf('=');
  if (eqIdx == -1) {
    Serial.print("Invalid mapping: ");
    Serial.println(cmd);
    return;
  }

  String meter = cmd.substring(0, eqIdx);
  String metric = cmd.substring(eqIdx + 1);

  int idx = findOrAddMetric(metric);

  if (meter == "METER1") {
    mapM1 = idx;
    Serial.print("Mapped METER1 to ");
    Serial.println(metric);
  } else if (meter == "METER2") {
    mapM2 = idx;
    Serial.print("Mapped METER2 to ");
    Serial.println(metric);
  } else if (meter == "METER3") {
    mapM3 = idx;
    Serial.print("Mapped METER3 to ");
    Serial.println(metric);
  } else {
    Serial.print("Unknown meter: ");
    Serial.println(meter);
  }
}

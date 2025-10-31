#include <Wire.h>
#include "Adafruit_LEDBackpack.h"
#include "Adafruit_GFX.h"

// Create 3 display objects at different I2C addresses
Adafruit_7segment display1 = Adafruit_7segment();
Adafruit_7segment display2 = Adafruit_7segment();
Adafruit_7segment display3 = Adafruit_7segment();

Adafruit_7segment displays[] = {
  display1, display2, display3
};
// Assign addresses (set by jumpers on the boards)
#define ADDR1 0x70
#define ADDR2 0x71
#define ADDR3 0x72

void setupSegment() {
  Wire.begin();

  // Initialize displays
  display1.begin(ADDR1);
  display2.begin(ADDR2);
  display3.begin(ADDR3);

  // Set brightness (0–15)
  display1.setBrightness(5);
  display2.setBrightness(5);
  display3.setBrightness(5);

  // Clear at startup
  display1.clear(); display1.writeDisplay();
  display2.clear(); display2.writeDisplay();
  display3.clear(); display3.writeDisplay();
}

void setSegment(int value, int display_num) {
  // Write numbers
  display1.print(display_num);
  // display2.print(counter2);
  // display3.print(counter3);
}

void render() 
{
  display1.writeDisplay();
  display2.writeDisplay();
  display3.writeDisplay();
}

void loopSegment() {
  // Example: count up on each display independently
  static int counter1 = 0;
  static int counter2 = 100;
  static int counter3 = 200;

  // Write numbers
  display1.print(counter1);
  display2.print(counter2);
  display3.print(counter3);

  // Push updates
  display1.writeDisplay();
  display2.writeDisplay();
  display3.writeDisplay();

  // Increment counters
  counter1++;
  counter2 += 2;
  counter3 += 3;

  // Reset if too big
  if (counter1 > 9999) counter1 = 0;
  if (counter2 > 9999) counter2 = 0;
  if (counter3 > 9999) counter3 = 0;

  delay(500);
}

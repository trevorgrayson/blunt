/*
Voices
======
| Voice # | Name   | Gender | Description                                          |
| ------- | ------ | ------ | ---------------------------------------------------- |
| 0       | Paul   | Male   | Default voice. Natural-sounding American male voice. |
| 1       | Harry  | Male   | Older male voice with deeper pitch.                  |
| 2       | Frank  | Male   | Slightly monotone, “robotic” male voice.             |
| 3       | Dennis | Male   | Brighter, higher-pitched male voice.                 |
| 4       | Kit    | Female | Pleasant, natural-sounding American female voice.    |
| 5       | Ursula | Female | Deeper female voice, authoritative tone.             |
| 6       | Rita   | Female | Brighter, faster-paced female voice.                 |
| 7       | Wendy  | Female | Youthful, higher-pitched female voice.               |
| 8       | Betty  | Female | British accent female voice (light British).         |
*/

#include <SoftwareSerial.h>

// Pins for Uno <-> Emic 2
static const uint8_t EMIC_RX = 10; // Arduino RX  <- Emic SOUT (TX)
static const uint8_t EMIC_TX = 11; // Arduino TX  -> Emic SIN (RX)
static const uint8_t EMIC_RST = 2; // Optional reset (active LOW)

SoftwareSerial emic(EMIC_RX, EMIC_TX); // RX, TX

void voiceWaitForReady() {
  // Emic 2 signals readiness with a single ':' character
  while (true) {
    if (emic.available()) {
      if (emic.read() == ':') return;
    }
  }
}

void say(const char* text) {
  // Emic 2 "S" command => Speak until newline
  emic.print('S');
  emic.print(text);
  emic.print('\n');        // newline terminates the command
  voiceWaitForReady();          // block until speech finished and ':' received
}

void voiceSetup() {
  pinMode(EMIC_RST, OUTPUT);
  digitalWrite(EMIC_RST, HIGH);   // keep high (not in reset)
  pinMode(EMIC_RX, INPUT);
  pinMode(EMIC_TX, OUTPUT);
  // Start host serial for debug (optional)
  Serial.begin(115200);
  while (!Serial) { ; }

  // Start Emic serial
  emic.begin(9600);
  emic.print('\n');
  delay(10);
  emic.flush();
  // Hardware reset pulse (optional but robust)
  // digitalWrite(EMIC_RST, LOW);
  // delay(10);
  // digitalWrite(EMIC_RST, HIGH);

  // Emic 2 sends a startup message then ':' when ready
  voiceWaitForReady();
  emic.print("V");
  emic.print(18);
  emic.print("\n");
  // Example: set voice (optional). "N" command selects voice number.
  // Voices vary by firmware; voice 0 is common.
  // emic.print("N0\n");
  // voiceWaitForReady();

  // Speak a line
  // say("Hello! I am the Parallax Emic two text to speech module.");
  // say("Integration with Arduino Uno is complete.");
}

// void voiceTick() {
//   // Demo: say the time every 5 seconds (replace with your own triggers)
//   static uint32_t last = 0;
//   if (millis() - last > 5000UL) {
//     last = millis();
//     speak("This is a periodic test of the speech system.");
//   }
// }

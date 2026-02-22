#include <Arduino.h>
#include <ESP32Servo.h>

Servo myServo;

const int SERVO_PIN = 18;   // Change if needed

String inputBuffer = "";

void setup() {
    Serial.begin(115200);
    myServo.attach(SERVO_PIN);
    myServo.write(90);  // Start centered
}

void handleCommand(String cmd) {
    cmd.trim();

    if (cmd.startsWith("ANGLE")) {
        int spaceIndex = cmd.indexOf(' ');
        if (spaceIndex > 0) {
            int angle = cmd.substring(spaceIndex + 1).toInt();

            if (angle >= 0 && angle <= 180) {
                myServo.write(angle);
                Serial.println("OK");
            } else {
                Serial.println("ERR:ANGLE_RANGE");
            }
        }
    } else {
        Serial.println("ERR:UNKNOWN_CMD");
    }
}

void loop() {
    while (Serial.available()) {
        char c = Serial.read();

        if (c == '\n') {
            handleCommand(inputBuffer);
            inputBuffer = "";
        } else {
            inputBuffer += c;
        }
    }
}
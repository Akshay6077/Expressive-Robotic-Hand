#include <Arduino.h>
#include <Servo.h>

const int numberOfMotors = 5;
const int controlPins[numberOfMotors] = {8, 9, 10, 11, 12}; // Control pins for each servo
Servo servos[numberOfMotors]; // Servo objects
int currentPositions[numberOfMotors] = {0, 0, 180, 180, 0}; // Current position of each servo (in degrees)

String incomingString = ""; // To hold the incoming serial data

void setup() {
  Serial.begin(9600);
  // Attach each servo to its control pin
  for (int i = 0; i < numberOfMotors; i++) {
    servos[i].attach(controlPins[i]);
  }
  Serial.println("Ready to receive angle positions for servos, separated by commas.");
}

void loop() {
  if (Serial.available() > 0) {
    incomingString = Serial.readStringUntil('\n');
    processIncomingString(incomingString);
  }
}

void processIncomingString(String data) {
  int motorIndex = 0;
  int fromIndex = 0;
  while (motorIndex < numberOfMotors && fromIndex != -1) {
    int endIndex = data.indexOf(',', fromIndex);
    if (endIndex == -1) { // If it's the last number in the string
      endIndex = data.length();
    }
    int targetPosition = data.substring(fromIndex, endIndex).toInt();
    if (targetPosition != currentPositions[motorIndex]) {
      servos[motorIndex].write(targetPosition); // Set servo position
      currentPositions[motorIndex] = targetPosition;
    }
    fromIndex = endIndex + 1;
    motorIndex++;
  }
}

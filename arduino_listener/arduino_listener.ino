/*
 * Soft Robotics Control Board - Direct Command Listener (Uno R3)
 * Project: PneuNet Curvature Study - Software Bypass Mode
 * Protocol: START:<CH>:<TIME_MS>
 */

// --- HARDWARE MAPPING ---
const int valvePins[]  = {5, 6, 7, 8};    // Channels 1-4 (Solenoids)
// Note: switchPins and knobPins are kept for mapping reference but unused in loop
const int switchPins[] = {12, 11, 10, 9}; 
const int knobPins[]   = {A3, A2, A1, A0};
const int freqPin      = A5;

// --- STATE MANAGEMENT ---
unsigned long startTimes[4] = {0, 0, 0, 0};
unsigned long durations[4]  = {0, 0, 0, 0};
bool channelActive[4]       = {false, false, false, false};

void setup() {
  Serial.begin(115200);
  
  for (int i = 0; i < 4; i++) {
    pinMode(valvePins[i], OUTPUT);
    digitalWrite(valvePins[i], LOW);
    // Pins 12, 11, 10, 9 are no longer set as INPUT_PULLUP to ignore them
  }
  
  Serial.println("STATUS:READY");
}

void loop() {
  checkSerial();
  updateValves();
}

void checkSerial() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    // Emergency Software Abort
    if (input == "ABORT") {
      abortAll();
    } 
    // Handle Pulse Command
    else if (input.startsWith("START:")) {
      int firstColon = input.indexOf(':');
      int secondColon = input.indexOf(':', firstColon + 1);
      
      if (firstColon != -1 && secondColon != -1) {
        int ch = input.substring(firstColon + 1, secondColon).toInt();
        unsigned long dur = input.substring(secondColon + 1).toInt();
        
        if (ch >= 1 && ch <= 4) {
          int idx = ch - 1;
          durations[idx] = dur;
          startTimes[idx] = millis();
          channelActive[idx] = true;
          
          // Python driver expects this to enter busy state
          Serial.print("STATUS:BUSY:CH");
          Serial.println(ch);
        }
      }
    }
  }
}

void updateValves() {
  for (int i = 0; i < 4; i++) {
    if (channelActive[i]) {
      unsigned long elapsed = millis() - startTimes[i];
      
      if (elapsed >= durations[i]) {
        // TIMER EXPIRED
        digitalWrite(valvePins[i], LOW);
        channelActive[i] = false;
        
        // Python driver expects this to finish the trial
        Serial.print("STATUS:DONE:CH");
        Serial.println(i + 1);
      } else {
        // VALVE COMMAND: Direct High (Ignores physical switches)
        digitalWrite(valvePins[i], HIGH);
      }
    } else {
      // Ensure valve stays closed when not active
      digitalWrite(valvePins[i], LOW);
    }
  }
}

void abortAll() {
  for (int i = 0; i < 4; i++) {
    digitalWrite(valvePins[i], LOW);
    channelActive[i] = false;
  }
  Serial.println("STATUS:ABORT_COMPLETE");
}
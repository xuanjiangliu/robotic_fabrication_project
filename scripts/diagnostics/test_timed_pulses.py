import sys
import os
import time
import logging

# Adhering to project architecture for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pkg.drivers.pneumatic_serial import PneumaticSerial

# --- CONFIGURATION ---
ARDUINO_PORT = "COM5"
TEST_CHANNEL = 4
PULSE_DURATIONS = [500, 1000, 1500, 2000, 2500] # Target PhD study intervals

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [Diagnostic] - %(message)s')
logger = logging.getLogger()

def run_pulse_sequence():
    logger.info("--- Starting Timed Pulse Diagnostic (No Vision) ---")
    
    # Initialize connection to Arduino Uno R3 on COM5
    pneumatic = PneumaticSerial(port=ARDUINO_PORT)
    
    if not pneumatic.ser or not pneumatic.ser.is_open:
        logger.error(f"❌ Could not connect to Arduino on {ARDUINO_PORT}. Check USB connection.")
        return

    try:
        for duration in PULSE_DURATIONS:
            print(f"\n--- TRIAL: {duration}ms ---")
            print(f"Action: Pulse Channel {TEST_CHANNEL} for {duration}ms")
            input("👉 Press ENTER to trigger pulse...")

            # 1. Trigger the Pulse (Outbound: START:CH:TIME)
            if pneumatic.start_pulse(TEST_CHANNEL, duration):
                logger.info(f"Pulse active on CH{TEST_CHANNEL}...")
                
                # 2. Asynchronous Wait (Polling for STATUS:DONE)
                start_time = time.time()
                while pneumatic.is_busy():
                    elapsed = (time.time() - start_time) * 1000
                    # Standard non-blocking poll
                    time.sleep(0.01) 
                
                logger.info(f"✅ Handshake received. Arduino finished in {elapsed:.0f}ms.")
            else:
                logger.error("Failed to start pulse. Check if Arduino is busy or disconnected.")
                break

            # Manual break between intervals for actuator resetting
            input("👉 Reset/Vent actuator and press ENTER for next duration...")

    except KeyboardInterrupt:
        logger.warning("\nSequence aborted by user.")
    finally:
        pneumatic.close()
        logger.info("Connection closed. Diagnostic complete.")

if __name__ == "__main__":
    run_pulse_sequence()
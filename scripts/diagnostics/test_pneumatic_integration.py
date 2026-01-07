import sys
import os
import time
import logging

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from pkg.drivers.pneumatic_serial import PneumaticSerial #

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')

def main():
    # 1. Initialize Connection
    # Uses COM5 as specified for your Arduino Uno R3
    pneumatic = PneumaticSerial(port="COM5", baud=115200) #
    
    if not pneumatic.ser:
        print("❌ Could not open COM5. Check your USB connection and Serial Monitor.")
        return

    print("\n--- Pneumatic System Diagnostic ---")
    print("This test will pulse Channel 4 for 2 seconds.")
    print("1. Ensure 12V/24V power is connected to the solenoids.")
    print("2. Ensure the physical toggle switch for CH4 is in the 'ON' position.")
    input("👉 Press ENTER to start the pulse...")

    # 2. Start the Pulse
    # Format: Channel 4, 2000ms
    if pneumatic.start_pulse(4, 2000): #
        print("🚀 Pulse started! Watching for 'DONE' signal...")
        
        # 3. Demonstrate Non-Blocking Behavior
        # While the solenoid is open, we can still run code (like vision)
        start_time = time.time()
        while pneumatic.is_busy(): #
            elapsed = time.time() - start_time
            print(f"⏳ Waiting... Valve is OPEN ({elapsed:.1f}s)", end='\r')
            time.sleep(0.1)
        
        print(f"\n✅ Success! Received Handshake from Arduino.")
    else:
        print("❌ Failed to start pulse.")

    # 4. Test Abort Logic
    print("\n--- Testing Emergency Abort ---")
    print("Starting a 5-second pulse. We will abort it after 1 second.")
    input("👉 Press ENTER to start...")
    
    pneumatic.start_pulse(4, 5000) #
    time.sleep(1.0)
    pneumatic.abort() #
    
    if not pneumatic.is_busy(): #
        print("✅ Abort successful. Valve closed early.")

    pneumatic.close() #
    print("\nDiagnostic Complete.")

if __name__ == "__main__":
    main()
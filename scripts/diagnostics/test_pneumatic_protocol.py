import sys
import os
import logging

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pkg.drivers.pneumatic_serial import MockPneumaticSerial

def main():
    logging.basicConfig(level=logging.INFO)
    print("--- Diagnostic: Pneumatic Serial Protocol ---")
    
    # Initialize mock driver
    pneumatic = MockPneumaticSerial(port='COM_FAKE')
    
    test_cases = [
        {'ch': 1, 'time': 500},
        {'ch': 2, 'time': 1500},
    ]
    
    for test in test_cases:
        print(f"\n▶️ Testing Channel {test['ch']} for {test['time']}ms...")
        success = pneumatic.send_pulse(test['ch'], test['time'])
        if success:
            print(f"✅ Pulse cycle completed for Channel {test['ch']}")
            
    pneumatic.close()

if __name__ == "__main__":
    main()
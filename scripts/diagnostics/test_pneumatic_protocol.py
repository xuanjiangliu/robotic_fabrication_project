# scripts/diagnostics/test_pneumatic_protocol.py
import time
from pkg.drivers.pneumatic_serial import MockPneumaticSerial

def test_async_pulse():
    pneumatic = MockPneumaticSerial()
    
    print("Starting a 2-second pulse...")
    pneumatic.start_pulse(1, 2000)
    
    count = 0
    while pneumatic.is_busy():
        print(f"Looping... (Vision Frame #{count})")
        count += 1
        time.sleep(0.1) # Simulate a 10Hz vision loop
        
    print("Done! Main loop was never blocked.")

if __name__ == "__main__":
    test_async_pulse()
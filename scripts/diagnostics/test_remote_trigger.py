import sys
import os
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pkg.drivers.robotiq_v2 import RTDETriggerClient

ROBOT_IP = "192.168.50.82"

def main():
    client = RTDETriggerClient(ROBOT_IP)
    
    # 1. Connect
    if not client.connect():
        return

    # 2. Safety Check
    if not client.is_program_running():
        print("⚠️ WARNING: The robot program is NOT running!")
        print("   Action: Go to Tablet, load 'driver_loop.urp', and press PLAY.")
        print("   The robot should sit at the 'Wait' node.")
        input("   Press ENTER once you have started the robot program...")

    # 3. Trigger
    print("\n🚀 Attempting to trigger the cycle...")
    client.trigger_cycle()
    
    print("⏳ Waiting 5 seconds to simulate cycle...")
    time.sleep(5)
    
    print("✅ Test Complete.")
    client.disconnect()

if __name__ == "__main__":
    main()
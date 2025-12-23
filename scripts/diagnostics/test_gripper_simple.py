import sys
import os
import time

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pkg.drivers.ur_rtde_wrapper import URRobot

ROBOT_IP = "192.168.50.82"

def test_gripper_simple():
    print(f"--- Simple Gripper Test (Modbus) ---")
    print(f"Target: {ROBOT_IP}")
    
    bot = URRobot(ROBOT_IP)
    
    # 1. Connect & Activate
    print("\n1. Connecting...")
    print("   (Watch the Gripper LED -> Should turn SOLID BLUE)")
    
    if not bot.connect():
        print("❌ Failed to connect.")
        return

    print("\n✅ Connected. Starting Cycle Loop...")
    
    # 2. Test Loop
    for i in range(3):
        print(f"\nCycle {i+1}: Closing...")
        bot.gripper_close()
        time.sleep(3)
        
        print(f"Cycle {i+1}: Opening...")
        bot.gripper_open()
        time.sleep(3)

    print("\n✅ Test Complete.")
    bot.disconnect()

if __name__ == "__main__":
    test_gripper_simple()
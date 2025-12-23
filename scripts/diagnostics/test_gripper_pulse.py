import sys
import os
import time

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.drivers.ur_rtde_wrapper import URRobot

ROBOT_IP = "192.168.50.82"

def test_pulse_logic():
    print("--- RoboFab Gripper Pulse Test ---")
    print("Pre-requisite: 'driver_loop' must be PLAYING on the tablet.")
    
    bot = URRobot(ROBOT_IP)
    
    if not bot.connect():
        print("❌ Failed to connect.")
        return

    print("\n1. Pulse CLOSE (Reg 24 -> 1 -> 0)")
    bot.gripper_close()
    
    print("   Waiting 3 seconds for physical movement...")
    time.sleep(3)
    
    print("\n2. Pulse OPEN (Reg 24 -> 2 -> 0)")
    bot.gripper_open()
    
    print("   Waiting 3 seconds...")
    time.sleep(3)
    
    print("\n✅ Test Complete.")
    bot.disconnect()

if __name__ == "__main__":
    test_pulse_logic()
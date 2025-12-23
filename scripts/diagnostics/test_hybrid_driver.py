import sys
import os
import time

# Add src to path so we can import the driver
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.drivers.ur_rtde_wrapper import URRobot

ROBOT_IP = "192.168.50.82"

def test_hybrid():
    bot = URRobot(ROBOT_IP)
    if not bot.connect():
        print("Failed to connect.")
        return

    # 1. Test Reading (Eyes)
    q = bot.get_joint_angles()
    
    # SAFETY CHECK: Ensure we actually got data before proceeding
    if q is None:
        print("Error: Could not read joint angles from robot.")
        return
        
    print(f"Current Joints: {q}")

    # 2. Test Moving (Hands)
    # Move Base joint +10 degrees (approx 0.17 rad) relative to current
    target_q = list(q)
    target_q[0] += 0.17
    
    print("Moving robot in 3 seconds... STAND CLEAR")
    time.sleep(3)
    
    bot.move_j(target_q, speed=0.5, acceleration=0.5)
    
    # Wait for move to start (latency buffer)
    time.sleep(0.5)
    
    # Monitor motion
    while bot.is_moving():
        # FIX: Use the new safe getter method instead of raw access
        speeds = bot.get_joint_speeds()
        print(f"Robot is moving... Velocity: {speeds[0]:.4f}")
        time.sleep(0.2)
        
    print("Motion complete.")
    bot.stop()

if __name__ == "__main__":
    test_hybrid()
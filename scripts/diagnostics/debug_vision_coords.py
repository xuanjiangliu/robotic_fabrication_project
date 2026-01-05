import sys
import os
import time
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pkg.drivers.ur_rtde_wrapper import URRobot
from pkg.vision.eye_in_hand import EyeInHand

ROBOT_IP = "192.168.50.82"

def main():
    print("--- VISION COORDINATE DEBUGGER ---")
    bot = URRobot(ROBOT_IP)
    if not bot.connect(): return
    
    vision = EyeInHand()
    
    print("\n1. Move Robot to where it can see the Benchy.")
    print("2. Looking at the loaded calibration:")
    print(f"   OFFSET: {vision.matrix_cam2gripper[:3,3]}")
    
    input("Press ENTER to Calculate Target (No Motion)...")
    
    pose = bot.get_tcp_pose()
    if not pose:
        print("❌ No Pose Data.")
        return

    # Simulate a center-screen detection (Pixel 640, 360)
    # This tells us where the robot thinks the center of the camera is looking
    tx, ty = vision.pixel_to_robot(640, 360, pose)
    
    print(f"\n[ROBOT POSE] X: {pose[0]:.3f}, Y: {pose[1]:.3f}, Z: {pose[2]:.3f}")
    print(f"[CALC TARGET] X: {tx:.3f}, Y: {ty:.3f}")
    
    print("\n⚠️ ANALYSIS:")
    if ty < -0.8:
         print(f"   -> Y={ty:.3f} is likely OUT OF REACH (limit ~ -0.8m).")
         print("   -> Your Y-Offset (-0.38) + Robot Y is pushing it too far.")
         print("   -> SUGGESTION: Recalibrate Camera or Check Mounting.")
    else:
         print("   -> Target looks reachable.")

    bot.disconnect()

if __name__ == "__main__":
    main()
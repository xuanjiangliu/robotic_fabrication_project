import sys
import os
import time

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pkg.drivers.ur_rtde_wrapper import URRobot

ROBOT_IP = "192.168.50.82"

def main():
    print("--- Simple Movement Test ---")
    
    # 1. Connect
    bot = URRobot(ROBOT_IP)
    if not bot.connect():
        print("❌ Could not connect to robot.")
        return

    # 2. Get Current Position (Safe Start)
    current_pose = bot.get_tcp_pose()
    if current_pose is None:
        print("❌ Could not read current pose.")
        return
    
    print(f"📍 Current Pose: {current_pose[:3]}")

    # 3. Calculate Target (Current Z + 0.05m)
    target_pose = list(current_pose)
    target_pose[2] += 0.05  # Move UP 50mm

    print(f"🎯 Target Pose:  {target_pose[:3]} (Moving UP 5cm)")
    print("⚠️  WARNING: Robot will move immediately.")
    input("👉 Press ENTER to execute...")

    # 4. Execute Move
    start_time = time.time()
    success = bot.move_linear(target_pose, speed=0.1) # Slow speed
    
    if success:
        print(f"✅ SUCCESS! Robot moved in {time.time() - start_time:.2f}s")
        
        # Optional: Move back down
        print("Moving back down...")
        bot.move_linear(current_pose, speed=0.1)
        print("Done.")
    else:
        print("❌ TEST FAILED: Robot rejected the move.")
        print("CHECK:")
        print("1. Is the robot in 'Remote Control' mode on the pendant?")
        print("2. Is the E-Stop released?")
        print("3. Is the robot already at the very top of its reach?")

    bot.disconnect()

if __name__ == "__main__":
    main()
import sys
import os
import time

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from pkg.drivers.ur_rtde_wrapper import URRobot

ROBOT_IP = "192.168.50.82"

def test_safety_stop():
    print("--- RoboFab Safety Stop Test ---")
    bot = URRobot(ROBOT_IP)
    
    if not bot.connect():
        print("❌ Failed to connect.")
        return

    # 1. Get Start Position
    q_start = bot.get_joint_angles()
    if not q_start:
        print("❌ Could not read joints (Start).")
        return

    # 2. Define a Long, Slow Move (Rotate Base +45 degrees)
    q_target = list(q_start)
    q_target[0] += 0.78  # ~45 degrees
    
    print(f"Start: {q_start}")
    print(f"Target: {q_target}")
    print("Initiating long move... (Will attempt STOP in 0.5s)")
    
    # 3. Fire the Move (Slow speed)
    bot.move_j(q_target, speed=0.3, acceleration=0.2)
    
    # 4. Wait briefly to let it accelerate
    time.sleep(0.5)
    
    # 5. EMERGENCY STOP
    print("🛑 TRIGGERING SOFT STOP 🛑")
    bot.stop()
    
    # 6. Verify Motion Stopped
    time.sleep(0.5) # Wait for deceleration
    
    if bot.is_moving():
        print("❌ FAILED: Robot is still moving!")
    else:
        print("✅ SUCCESS: Robot stopped mid-trajectory.")
        
    # 7. Calculate Distance Traveled (With Safety Check)
    q_end = bot.get_joint_angles()
    
    if q_end:
        diff = abs(q_end[0] - q_start[0])
        print(f"Distance traveled before stop: {diff:.4f} rad (Expected < 0.78)")
    else:
        print("⚠️ Could not read final position to verify distance.")

if __name__ == "__main__":
    test_safety_stop()
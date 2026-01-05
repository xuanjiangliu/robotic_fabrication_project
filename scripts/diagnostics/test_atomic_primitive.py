import sys
import os
import time

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pkg.drivers.ur_rtde_wrapper import URRobot

ROBOT_IP = "192.168.50.82"

def main():
    print("--- TESTING ATOMIC SCRIPT INJECTION ---")
    bot = URRobot(ROBOT_IP)
    if not bot.connect():
        print("❌ Failed to connect to robot.")
        return

    print("\n⚠️ WARNING: Robot will move vertically (Z) by 5cm.")
    print("Ensure the area is clear.")
    input("Press ENTER to execute transaction...")

    # --- PYLANCE FIX: Check for None ---
    pose = bot.get_tcp_pose()
    if pose is None:
        print("❌ Error: Could not read TCP pose. Robot might be disconnected.")
        return
        
    # Now it is safe to access indices
    z_start = pose[2]
    z_up = z_start + 0.05
    print(f"   [Reference] Start Z: {z_start:.4f}, Target Z: {z_up:.4f}")

    # Create a simple "Bob" script (Up 5cm -> Wait -> Down 5cm)
    script = f"""
        # Move UP
        movel(p[{pose[0]}, {pose[1]}, {z_up}, {pose[3]}, {pose[4]}, {pose[5]}], a=0.5, v=0.2)
        sleep(1.0)
        # Move DOWN
        movel(p[{pose[0]}, {pose[1]}, {z_start}, {pose[3]}, {pose[4]}, {pose[5]}], a=0.5, v=0.2)
    """

    success = bot.execute_atomic_script(script)
    
    if success:
        print("✅ SUCCESS: Robot executed script and returned.")
    else:
        print("❌ FAILURE: Script rejected or timed out.")

    bot.disconnect()

if __name__ == "__main__":
    main()
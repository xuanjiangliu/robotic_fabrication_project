import sys
import os
import json
import time
import numpy as np

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from pkg.drivers.ur_rtde_wrapper import URRobot

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '../../config/printer_cage.json')

# The 8 Corners of the Cube + 1 Entry Point
# We use standard Cartesian names: Left/Right, Front/Back, Bottom/Top
# Front = Near the Door/User. Back = Deep inside printer.
CAGE_SEQUENCE = [
    # --- BOTTOM PLANE (Near Print Bed) ---
    {"key": "corner_bottom_left_front",  "desc": "BOTTOM LEFT FRONT - (Near Door, Left Side, Low)"},
    {"key": "corner_bottom_right_front", "desc": "BOTTOM RIGHT FRONT - (Near Door, Right Side, Low)"},
    {"key": "corner_bottom_left_back",   "desc": "BOTTOM LEFT BACK - (Deep inside, Left Side, Low)"},
    {"key": "corner_bottom_right_back",  "desc": "BOTTOM RIGHT BACK - (Deep inside, Right Side, Low)"},

    # --- TOP PLANE (Near Ceiling) ---
    {"key": "corner_top_left_front",     "desc": "TOP LEFT FRONT - (Near Door, Left Side, High)"},
    {"key": "corner_top_right_front",    "desc": "TOP RIGHT FRONT - (Near Door, Right Side, High)"},
    {"key": "corner_top_left_back",      "desc": "TOP LEFT BACK - (Deep inside, Left Side, High)"},
    {"key": "corner_top_right_back",     "desc": "TOP RIGHT BACK - (Deep inside, Right Side, High)"},

    # --- ENTRY POINT ---
    {"key": "entry_pose",                "desc": "SAFE ENTRY POSE - (Hovering in front of door, ELBOW UP!)"}
]

def teach_cage_interactive():
    print("--- RoboFab 8-Point Cage Teacher ---")
    print(f"Connecting to robot at {ROBOT_IP}...")

    bot = URRobot(ROBOT_IP)
    if not bot.connect():
        print("❌ Robot Connection Failed. Check IP/Tablet.")
        return

    captured_data = {}
    
    print("\nStarting 8-Point Teaching Sequence.")
    print("CRITICAL: Maintain the 'Crane' (Elbow Up) shape for ALL points!")
    print("Jog to the position and press ENTER.")
    print("-" * 60)

    try:
        # 1. Capture Points
        for item in CAGE_SEQUENCE:
            print(f"\n📍 TEACHING: {item['key'].upper()}")
            print(f"📝 {item['desc']}")
            
            while True:
                user_in = input("👉 Jog & PRESS ENTER (or 's' to skip): ")
                if user_in.lower() == 's':
                    print("   Skipped.")
                    break
                
                # Capture FULL Pose [x, y, z, rx, ry, rz]
                pose = bot.get_tcp_pose()
                
                if pose:
                    print(f"   Captured: {[round(x, 4) for x in pose]}")
                    captured_data[item['key']] = pose
                    break 
                else:
                    print("   ❌ Read Error. Try again.")

        # 2. Process Data (Calculate Bounding Box)
        if captured_data:
            print("\nCalculating Safety Bounding Box...")
            
            # Extract all X, Y, Z values from the captured corners
            all_x = []
            all_y = []
            all_z = []
            
            for key, pose in captured_data.items():
                if key == 'entry_pose': continue # Don't let entry point expand the cage size
                all_x.append(pose[0])
                all_y.append(pose[1])
                all_z.append(pose[2])

            if all_x: # If we captured at least one corner
                # Calculate Min/Max
                x_min, x_max = min(all_x), max(all_x)
                y_min, y_max = min(all_y), max(all_y)
                z_min, z_max = min(all_z), max(all_z)

                # Apply Safety Buffer (Contract the box inwards by 5mm)
                BUFFER = 0.005
                captured_data['x_min'] = x_min + BUFFER
                captured_data['x_max'] = x_max - BUFFER
                captured_data['y_min'] = y_min + BUFFER
                captured_data['y_max'] = y_max - BUFFER
                captured_data['z_min'] = z_min + BUFFER
                captured_data['z_max'] = z_max - BUFFER

                print(f"   X Range: {captured_data['x_min']:.4f} to {captured_data['x_max']:.4f}")
                print(f"   Y Range: {captured_data['y_min']:.4f} to {captured_data['y_max']:.4f}")
                print(f"   Z Range: {captured_data['z_min']:.4f} to {captured_data['z_max']:.4f}")
            
            # 3. Save to JSON
            print("\n💾 SAVING TO config/printer_cage.json ...")
            os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
            with open(OUTPUT_FILE, 'w') as f:
                json.dump(captured_data, f, indent=4)
                
            print("✅ Configuration Saved.")

        else:
            print("\nNo data captured.")

    except KeyboardInterrupt:
        print("\n🚫 Aborted.")
    finally:
        bot.disconnect()

if __name__ == "__main__":
    teach_cage_interactive()
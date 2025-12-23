import sys
import os
import re
import shutil


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from pkg.drivers.ur_rtde_wrapper import URRobot

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
TARGET_FILE = os.path.join(PROJECT_ROOT, 'src', 'main.py')

# Define the sequence of waypoints to teach
WAYPOINT_SEQUENCE = [
    {"var_name": "HOME_JOINTS", "type": "joint", "desc": "SAFE HOME"},
    {"var_name": "PRE_GRASP_JOINTS", "type": "joint", "desc": "PRE-GRASP (Approach)"},
    {"var_name": "GRASP_POSE_L", "type": "pose", "desc": "GRASP POSE (Linear Entry)"},
    {"var_name": "EXIT_JOINTS", "type": "joint", "desc": "SAFETY EXIT"},
    {"var_name": "DROP_JOINTS", "type": "joint", "desc": "DROP ZONE"}
]

def update_file_variable(filepath, var_name, new_values):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    #  The Regex keeps the original file's brackets.
    new_inner_content = ", ".join([f"{x:.5f}" for x in new_values])

    # Regex captures: Group 1="VAR = [", Group 2="]"
    pattern = rf"({var_name}\s*=\s*\[).*?(\])"
    
    if not re.search(pattern, content):
        print(f"⚠️  Warning: Could not find variable '{var_name}' in main.py")
        return content

    # Replace the middle part with just the numbers
    new_content = re.sub(pattern, rf"\1{new_inner_content}\2", content, count=1)
    return new_content

def teach_mode():
    print("--- RoboFab AUTO-UPDATER TEACHER ---")
    
    bot = URRobot(ROBOT_IP)
    if not bot.connect():
        print("❌ Robot Connection Failed.")
        return

    if not os.path.exists(TARGET_FILE):
        print(f"❌ Error: Cannot find {TARGET_FILE}")
        return

    captured_data = {}

    try:
        print("\nStarting Sequence. Press Ctrl+C to abort.")
        for wp in WAYPOINT_SEQUENCE:
            print("="*60)
            print(f"📍 TEACHING: {wp['var_name']}")
            print(f"📝 Description: {wp['desc']}")
            print("-" * 60)
            
            while True:
                user_in = input("👉 Move robot & PRESS ENTER (or 's' to skip): ")
                if user_in.lower() == 's': break
                
                data = bot.get_joint_angles() if wp['type'] == 'joint' else bot.get_tcp_pose()

                if data:
                    print(f"   Captured: {[round(x, 4) for x in data]}")
                    if input("   Save? (y/n): ").lower() == 'y':
                        captured_data[wp['var_name']] = data
                        break
                else:
                    print("   ❌ Read Error.")

        if captured_data:
            print("\n💾 SAVING TO main.py ...")
            shutil.copy(TARGET_FILE, TARGET_FILE + ".bak")
            
            for var_name, values in captured_data.items():
                new_content = update_file_variable(TARGET_FILE, var_name, values)
                with open(TARGET_FILE, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"   ✅ Updated {var_name}")
                
            print("\n🎉 Done. Check main.py for clean brackets!")
        else:
            print("\nNo points captured.")

    except KeyboardInterrupt:
        print("\n🚫 Aborted.")
    finally:
        bot.disconnect()

if __name__ == "__main__":
    teach_mode()
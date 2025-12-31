import sys
import os
import json
import time
import socket

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
PORT = 30002
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '../../config/printer_cage.json')

# Speeds
SPEED_J = 0.5    # rad/s (Approach speed - Fast)
ACCEL_J = 0.5    # rad/s^2
SPEED_L = 0.05   # m/s (Cage Patrol Speed - SLOW)
ACCEL_L = 0.1    # m/s^2

def load_cage_config(path):
    if not os.path.exists(path):
        print(f"❌ Config file {path} not found!")
        sys.exit(1)
    with open(path, 'r') as f:
        return json.load(f)

def fmt_pose(p):
    """Formats a list [x,y,z,rx,ry,rz] into a URScript pose string p[x,y,z,...]"""
    # Ensure we use exactly 6 decimals for precision
    return f"p[{p[0]:.6f}, {p[1]:.6f}, {p[2]:.6f}, {p[3]:.6f}, {p[4]:.6f}, {p[5]:.6f}]"

def main():
    print("--- RoboFab Cage Patrol (Socket / PolyScope X) ---")
    
    # 1. Load Config
    cage = load_cage_config(CONFIG_FILE)
    try:
        x_min, x_max = cage['x_min'], cage['x_max']
        y_min, y_max = cage['y_min'], cage['y_max']
        z_min, z_max = cage['z_min'], cage['z_max']
        entry_pose = cage['entry_pose']
        
        # Use Entry Rotation for stability (Elbow Up)
        fixed_rot = entry_pose[3:6] 
    except KeyError as e:
        print(f"❌ Malformed config: Missing {e}")
        return

    # 2. Define Waypoints 
    # Logic: Based on your logs, X_MIN = Left, Y_MAX = Front (Door)
    
    # START: Bottom Left Front (Door)
    start_corner = [x_min, y_max, z_min] + fixed_rot
    
    waypoints = [
        # --- Bottom Loop ---
        ("Bottom Left (Start)",  [x_min, y_max, z_min] + fixed_rot),
        ("Bottom Right (Door)",  [x_max, y_max, z_min] + fixed_rot),
        ("Bottom Right (Back)",  [x_max, y_min, z_min] + fixed_rot),
        ("Bottom Left (Back)",   [x_min, y_min, z_min] + fixed_rot),
        ("Bottom Left (Close)",  [x_min, y_max, z_min] + fixed_rot),
        
        # --- Move Up ---
        ("Top Left (Door)",      [x_min, y_max, z_max] + fixed_rot),
        
        # --- Top Loop ---
        ("Top Right (Door)",     [x_max, y_max, z_max] + fixed_rot),
        ("Top Right (Back)",     [x_max, y_min, z_max] + fixed_rot),
        ("Top Left (Back)",      [x_min, y_min, z_max] + fixed_rot),
        ("Top Left (Close)",     [x_min, y_max, z_max] + fixed_rot),
    ]

    # 3. Construct URScript
    # We send a single function to guarantee smooth execution without socket lag
    script = "def cage_patrol_seq():\n"
    
    # A. Move to Entry (Joint Move)
    script += f"  textmsg(\"Approaching Entry...\")\n"
    script += f"  movej({fmt_pose(entry_pose)}, a={ACCEL_J}, v={SPEED_J})\n"
    script += f"  sleep(0.5)\n"
    
    # B. Move to Start Corner (Linear)
    script += f"  textmsg(\"Moving to Start Corner...\")\n"
    script += f"  movel({fmt_pose(start_corner)}, a={ACCEL_L}, v={SPEED_L})\n"
    script += f"  sleep(0.5)\n"

    # C. Execute Patrol
    script += f"  textmsg(\"Starting Patrol...\")\n"
    for name, pt in waypoints:
        # Note: We don't send 'name' to robot, just pose
        script += f"  movel({fmt_pose(pt)}, a={ACCEL_L}, v={SPEED_L})\n"
    
    # D. Return to Entry
    script += f"  textmsg(\"Returning to Entry...\")\n"
    script += f"  movel({fmt_pose(entry_pose)}, a={ACCEL_L}, v={SPEED_L})\n"
    script += "end\n"
    
    # Run the function
    script += "cage_patrol_seq()\n"

    # 4. Send to Robot
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    
    try:
        print(f"Connecting to {ROBOT_IP}:{PORT}...")
        s.connect((ROBOT_IP, PORT))
        print("✅ Connected.")
        
        print("\n⚠️  WARNING: Robot will move AUTOMATICALLY.")
        print(f"    Sequence: Entry -> Bottom Left (Door) -> Loop -> Top -> Loop -> Entry")
        print("\n👉 Press Ctrl+C at ANY TIME to STOP immediately.")
        input("👉 PRESS ENTER TO START PATROL...")

        # Send
        s.sendall(script.encode('utf-8'))
        print("🚀 Script Sent! Robot moving...")

        # Monitor (Keep script alive for StopJ capability)
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            sys.stdout.write(f"\r⏳ Running... ({elapsed:.1f}s) | Press Ctrl+C to STOP")
            sys.stdout.flush()
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n\n🛑 STOPPING ROBOT (Ctrl+C Detected)!")
        try:
            # Immediate Stop
            s.sendall(b"stopj(2.0)\n")
            print("✅ Stop command sent.")
        except:
            print("❌ Failed to send stop.")
            
    except Exception as e:
        print(f"\n❌ Socket Error: {e}")
    finally:
        s.close()
        print("\nSocket closed.")

if __name__ == "__main__":
    main()
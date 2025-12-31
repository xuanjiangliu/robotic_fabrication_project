import sys
import os
import rtde_receive # type: ignore

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

ROBOT_IP = "192.168.50.82"

def get_mode_name(mode_int):
    # Mapping UR Robot Modes
    modes = {
        0: "DISCONNECTED",
        1: "CONFIRM_SAFETY",
        2: "BOOTING",
        3: "POWER_OFF",
        4: "POWER_ON",
        5: "IDLE",
        6: "BACKDRIVE",
        7: "RUNNING",
        8: "UPDATING_FIRMWARE"
    }
    return modes.get(mode_int, f"UNKNOWN ({mode_int})")

def get_safety_name(mode_int):
    # Mapping UR Safety Modes
    modes = {
        1: "NORMAL",
        2: "REDUCED",
        3: "PROTECTIVE_STOP",
        4: "RECOVERY",
        5: "SAFEGUARD_STOP",
        6: "SYSTEM_EMERGENCY_STOP",
        7: "ROBOT_EMERGENCY_STOP",
        8: "VIOLATION",
        9: "FAULT"
    }
    return modes.get(mode_int, f"UNKNOWN ({mode_int})")

def main():
    print(f"--- Checking Robot Status ({ROBOT_IP}) ---")
    try:
        r = rtde_receive.RTDEReceiveInterface(ROBOT_IP)
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return

    # Read Status
    r_mode = r.getRobotMode()
    s_mode = r.getSafetyMode()
    
    print(f"🔹 Robot Mode:  {r_mode} -> {get_mode_name(r_mode)}")
    print(f"🔹 Safety Mode: {s_mode} -> {get_safety_name(s_mode)}")
    
    # Diagnosis
    if s_mode != 1:
        print("\n❌ PROBLEM: Safety Stop Active!")
        print("   Action: Unlock the E-Stop or acknowledge the Protective Stop on the pendant.")
    elif r_mode != 7:
        print("\n❌ PROBLEM: Robot is not RUNNING.")
        print("   Action: You must press 'ON' -> 'START' (Release Brakes) on the pendant.")
        print("   The status light on the pendant must be SOLID GREEN.")
    else:
        print("\n✅ STATUS OK: Robot is ready to move.")
        print("   If moves still fail, check 'Remote Control' toggle in Settings.")

    r.disconnect()

if __name__ == "__main__":
    main()
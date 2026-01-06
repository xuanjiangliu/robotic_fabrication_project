import sys
import os
import time
import socket

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
PORT = 30002

# --- THE SCRIPT (Defined LOCALLY to prevent Ghost Imports) ---
# This matches your "Manual UI Setup" (Slave ID 1, Addr 0,1,2)
# It strictly uses NAMES, so the Tablet handles the Modbus mapping.
ACTIVATION_SCRIPT = """
def rq_activate_direct():
    textmsg("EVOFAB: Direct Activation (Bypass Mode)")

    # 1. Reset (Write 0 to Grip_CMD)
    modbus_set_output_register("Grip_CMD", 0)
    sleep(0.5)
    
    # 2. Set Force (Write to Grip_FOR)
    # 255 Speed (0xFF) + 150 Force (0x96) -> 65430
    modbus_set_output_register("Grip_FOR", 65430)
    sleep(0.1)

    # 3. Activate (Write 256 to Grip_CMD)
    modbus_set_output_register("Grip_CMD", 256)
    
    sleep(2.0)
end
rq_activate_direct()
"""

MOVE_CLOSE_SCRIPT = """
def rq_close_direct():
    textmsg("EVOFAB: Direct Close")
    modbus_set_output_register("Grip_POS", 255)
    sleep(0.1)
    modbus_set_output_register("Grip_CMD", 2304)
end
rq_close_direct()
"""

MOVE_OPEN_SCRIPT = """
def rq_open_direct():
    textmsg("EVOFAB: Direct Open")
    modbus_set_output_register("Grip_POS", 0)
    sleep(0.1)
    modbus_set_output_register("Grip_CMD", 2304)
end
rq_open_direct()
"""

def send_script(script):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((ROBOT_IP, PORT))
        s.sendall(script.encode('utf-8'))
        s.close()
        print("   ✅ Sent command to robot.")
        return True
    except Exception as e:
        print(f"   ❌ Socket Error: {e}")
        return False

def main():
    print(f"--- DIRECT Gripper Test (No Imports) ---")
    print(f"Target: {ROBOT_IP}")
    
    # 1. Activation
    print("\n1. Sending Activation Script...")
    if send_script(ACTIVATION_SCRIPT):
        print("   Waiting 4 seconds for 'Clack'...")
        time.sleep(4.0)

    # 2. Move Close
    print("\n2. Closing Gripper...")
    send_script(MOVE_CLOSE_SCRIPT)
    time.sleep(3.0)

    # 3. Move Open
    print("\n3. Opening Gripper...")
    send_script(MOVE_OPEN_SCRIPT)
    time.sleep(3.0)

    print("\n✅ Test Complete.")

if __name__ == "__main__":
    main()
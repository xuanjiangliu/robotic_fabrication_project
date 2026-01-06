import sys
import os
import time
import socket
import struct

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
PORT = 30002

# --- THE CLEAN URSCRIPT (Defined LOCALLY to prevent Ghost Imports) ---
# This script uses the signals you defined in the UI (Slave 1, Addr 0,1,2)
# It DOES NOT try to add/delete signals.
ACTIVATION_SCRIPT = """
def rq_activate_direct():
    textmsg("EVOFAB: Direct Activation (UI Mode)")

    # 1. Reset (Write 0 to Grip_CMD / Addr 0)
    # The Tablet handles the mapping to the hardware. We just use the Name.
    modbus_set_output_register("Grip_CMD", 0)
    sleep(0.5)
    
    # 2. Set Force (Write to Grip_FOR / Addr 2)
    # 255 Speed (0xFF) + 150 Force (0x96) -> 65430
    modbus_set_output_register("Grip_FOR", 65430)
    sleep(0.1)

    # 3. Activate (Write 256 to Grip_CMD / Addr 0)
    modbus_set_output_register("Grip_CMD", 256)
    
    sleep(2.0)
end
rq_activate_direct()
"""

def get_move_script(pos):
    pos = max(0, min(255, int(pos)))
    return f"""
def rq_move_direct():
    # 1. Set Position (Write to Grip_POS / Addr 1)
    modbus_set_output_register("Grip_POS", {pos})
    sleep(0.1)
    
    # 2. GoTo (Write 2304 to Grip_CMD / Addr 0)
    modbus_set_output_register("Grip_CMD", 2304)
end
rq_move_direct()
"""

# --- DIRECT SOCKET SENDER (Bypassing Wrapper) ---
def send_script(script):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((ROBOT_IP, PORT))
        s.sendall(script.encode('utf-8'))
        s.close()
        return True
    except Exception as e:
        print(f"❌ Socket Error: {e}")
        return False

# --- THE TEST SEQUENCE ---
def main():
    print(f"--- DIRECT Gripper Test (No Imports) ---")
    print(f"Target: {ROBOT_IP}")
    
    # 1. Activation
    print("\n1. Sending Activation Script...")
    print("   (Code being sent is DEFINED LOCALLY - No Ghost Files)")
    if send_script(ACTIVATION_SCRIPT):
        print("   ✅ Sent. Waiting 4 seconds for 'Clack'...")
        time.sleep(4.0)
    else:
        return

    # 2. Move Close
    print("\n2. Closing Gripper (255)...")
    send_script(get_move_script(255))
    time.sleep(3.0)

    # 3. Move Open
    print("\n3. Opening Gripper (0)...")
    send_script(get_move_script(0))
    time.sleep(3.0)

    print("\n✅ Test Complete.")

if __name__ == "__main__":
    main()
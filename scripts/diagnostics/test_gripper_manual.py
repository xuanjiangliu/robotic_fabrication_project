import sys
import os
import time
import socket

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
PORT = 30002

# --- THE MANUAL SETUP SCRIPT ---
# 1. We manually ADD the signals (Slave 1, Addr 0,1,2)
#    This replaces the UI setup that was crashing.
# 2. We use distinct names to be safe.
SCRIPT = """
def rq_manual_test():
    textmsg("EVOFAB: Starting Manual Setup...")

    # --- SETUP PHASE ---
    # Delete any potential ghosts first
    modbus_delete_signal("Man_CMD")
    modbus_delete_signal("Man_POS")
    modbus_delete_signal("Man_FOR")

    # Add Signals Manually
    # IP: "127.0.0.1", Slave: 1, Addr: 0/1/2, Type: 3 (Reg Out), Name: "..."
    modbus_add_signal("127.0.0.1", 1, 0, 3, "Man_CMD")
    modbus_add_signal("127.0.0.1", 1, 1, 3, "Man_POS")
    modbus_add_signal("127.0.0.1", 1, 2, 3, "Man_FOR")
    
    # Set Update Frequency (Optional but good practice)
    modbus_set_signal_update_frequency("Man_CMD", 10)
    
    textmsg("EVOFAB: Signals Added. Activating...")

    # --- ACTIVATION PHASE ---
    # 1. Reset
    modbus_set_output_register("Man_CMD", 0)
    sleep(0.5)
    
    # 2. Force/Speed (Max) -> 65430
    modbus_set_output_register("Man_FOR", 65430)
    sleep(0.1)

    # 3. Activate (256)
    modbus_set_output_register("Man_CMD", 256)
    
    sleep(2.0)
    textmsg("EVOFAB: Activated. Moving...")

    # --- MOTION PHASE ---
    # Close
    modbus_set_output_register("Man_POS", 255)
    sleep(0.1)
    modbus_set_output_register("Man_CMD", 2304) # GoTo + Activate
    sleep(2.0)

    # Open
    modbus_set_output_register("Man_POS", 0)
    sleep(0.1)
    modbus_set_output_register("Man_CMD", 2304)
    sleep(2.0)
    
    textmsg("EVOFAB: Test Complete")
end
rq_manual_test()
"""

def send_script():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((ROBOT_IP, PORT))
        s.sendall(SCRIPT.encode('utf-8'))
        s.close()
        print("✅ Script sent to robot.")
        return True
    except Exception as e:
        print(f"❌ Socket Error: {e}")
        return False

if __name__ == "__main__":
    print(f"--- Manual Gripper Setup Test ---")
    send_script()
import socket
import time

# --- Configuration for RoboFab UR7e ---
ROBOT_IP = "192.168.50.82"
PORT_30002 = 30002  # The Primary Scripting Port

# Define a RAW URScript that is PolyScope X compliant.
# We use a 'def' wrapper and explicit textmsg for logging.
SCRIPT_COMMAND = """
def my_move_test():
    textmsg("RoboFab: Script started")
    
    # Move to a safe relative position (Current Joint 0 + 10 degrees)
    # This prevents singularity or collision issues by using relative movement
    q_current = get_actual_joint_positions()
    q_target = q_current
    q_target[0] = q_target[0] + 0.17  # ~10 degrees offset on Base joint
    
    textmsg("RoboFab: Target calculated, moving...")
    
    # movej(q, a=1.2, v=0.25, t=0, r=0)
    # Using slow acceleration (0.5) and speed (0.25) for safety
    movej(q_target, a=0.5, v=0.25)
    
    textmsg("RoboFab: Motion complete")
end
"""

def send_script():
    print(f"--- RoboFab PolyScope X Diagnostic ---")
    print(f"Target: {ROBOT_IP}")
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((ROBOT_IP, PORT_30002))
        print("✅ Socket connected to Port 30002")
        
        # PolyScope expects a newline at the end of the script
        payload = (SCRIPT_COMMAND + "\n").encode('utf-8')
        s.sendall(payload)
        print("✅ Script payload sent")
        
        print("Check the PolyScope X Log tab immediately.")
        s.close()
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    send_script()
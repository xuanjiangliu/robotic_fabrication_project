import socket
import time

# Configuration
ROBOT_IP = "192.168.50.82"
PORT = 30002  # Primary Scripting Port

def send_script(script_code):
    """
    Wraps the raw URScript in a socket connection to the robot.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((ROBOT_IP, PORT))
        
        # URScript must end with a newline
        if not script_code.endswith("\n"):
            script_code += "\n"
            
        s.sendall(script_code.encode('utf-8'))
        s.close()
        print("   -> Command sent.")
    except Exception as e:
        print(f"   ❌ Connection Error: {e}")

def get_activation_script():
    # Connects to internal daemon at 127.0.0.1:63352
    return """
def rq_activate_direct():
    textmsg("RoboFab: Activating Gripper...")
    socket_open("127.0.0.1", 63352, "sock_rq")
    
    # ACT 1: Activate
    # SPE 255: Max Speed
    # FOR 50: Medium Force
    # GTO 1: Go To Position
    socket_send_line("SET ACT 1 SPE 255 FOR 50 GTO 1", "sock_rq")
    
    sync()
    sleep(0.5)
    socket_close("sock_rq")
end
rq_activate_direct()
"""

def get_move_script(pos):
    # pos: 0 (Open) to 255 (Closed)
    return f"""
def rq_move_direct():
    textmsg("RoboFab: Moving Gripper to {pos}...")
    socket_open("127.0.0.1", 63352, "sock_rq")
    
    # Standard move command
    command = "SET POS {pos} SPE 255 FOR 150 GTO 1 ACT 1"
    
    socket_send_line(command, "sock_rq")
    
    sync()
    sleep(0.2)
    socket_close("sock_rq")
end
rq_move_direct()
"""

def test_direct_control():
    print(f"--- RoboFab Direct Control Test ---")
    print(f"Target: {ROBOT_IP}:{PORT}")
    
    # 1. Activation
    print("\n1. Sending ACTIVATION Signal...")
    send_script(get_activation_script())
    print("   Waiting 3s for activation (Watch for Blue LED)...")
    time.sleep(3)

    # 2. Close
    print("\n2. Sending CLOSE Signal (255)...")
    send_script(get_move_script(255))
    print("   Waiting 3s...")
    time.sleep(3)

    # 3. Open
    print("\n3. Sending OPEN Signal (0)...")
    send_script(get_move_script(0))
    print("   Waiting 3s...")
    time.sleep(3)

    print("\n✅ Test Sequence Complete.")

if __name__ == "__main__":
    test_direct_control()
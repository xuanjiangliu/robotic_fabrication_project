
import sys
import os
import time
import socket
import struct

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# We use the wrapper only to read the current pose (Monitor)
from pkg.drivers.ur_rtde_wrapper import URRobot

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
HOST_IP = "0.0.0.0"
PORT = 50002

class BlindServer:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((HOST_IP, PORT))
        self.sock.listen(1)
        print(f"[Server] Listening on {HOST_IP}:{PORT}")

    def wait_for_robot(self):
        print("\n[Server] ⏳ Waiting for Robot request...")
        self.client, self.addr = self.sock.accept()
        print(f"[Server] ✅ Robot Connected from {self.addr}")
        return True

    def send_nod_script(self, current_pose):
        """
        Sends a script to move Up 5cm, then Down 5cm.
        """
        # Unpack current pose
        x, y, z, rx, ry, rz = current_pose
        
        # Target: 5cm higher
        z_up = z + 0.05
        
        # Format values safely
        # Note: We append 'external_move()' at the end so it actually runs!
        script = (
            "def external_move():\n"
            f"  p_start = p[{x}, {y}, {z}, {rx}, {ry}, {rz}]\n"
            f"  p_up    = p[{x}, {y}, {z_up}, {rx}, {ry}, {rz}]\n"
            "  textmsg(\"Server: Received Control. Nodding...\")\n"
            "  movej(p_up, a=0.5, v=0.25)\n"
            "  movej(p_start, a=0.5, v=0.25)\n"
            "end\n"
            "external_move()\n"
        )
        
        print("[Server] 📤 Sending 'Nod' Script...")
        self.client.send(script.encode('utf-8'))
        
        # Close connection to tell robot "Script download complete"
        self.client.close()
        print("[Server] 🏁 Connection Closed. Robot should be moving.")

    def close(self):
        self.sock.close()

def main():
    print("--- BLIND RELAY TEST ---")
    
    # 1. Connect Monitor (to read where we are)
    bot = URRobot(ROBOT_IP)
    if not bot.connect():
        print("❌ Failed to connect to Robot RTDE.")
        return

    # 2. Start Server
    server = BlindServer()

    try:
        while True:
            # A. Wait for Robot
            server.wait_for_robot()

            # B. Get Current Pose
            pose = bot.get_tcp_pose()
            if not pose:
                print("❌ Could not read pose. Closing request.")
                server.client.close()
                continue
            
            print(f"[Monitor] Current Z Height: {pose[2]:.4f}m")

            # C. Send Command
            server.send_nod_script(pose)
            
            # D. Wait for loop
            time.sleep(2.0)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        server.close()
        bot.disconnect()

if __name__ == "__main__":
    main()
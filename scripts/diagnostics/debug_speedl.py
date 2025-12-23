import socket
import time

ROBOT_IP = "192.168.50.82"
PORT = 30002

def test_move():
    print(f"Connecting to {ROBOT_IP}...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((ROBOT_IP, PORT))
        print("✅ Connected. Sending SPEEDL command...")
        
        # Send a command to move Z+ at 0.05 m/s (Very slow/safe)
        # We must send it in a loop because 'speedl' times out after 't' seconds
        t_duration = 0.1
        start_time = time.time()
        
        print("🚀 MOVING UP! Watch the robot.")
        while time.time() - start_time < 2.0:
            # speedl([x,y,z,rx,ry,rz], a, t)
            cmd = f"speedl([0,0,0.05,0,0,0], a=0.3, t={t_duration})\n"
            s.sendall(cmd.encode('utf-8'))
            time.sleep(t_duration / 2) # Send faster than timeout to keep it smooth
            
        # Stop
        s.sendall(b"stopj(2.0)\n")
        print("🛑 Done.")
        s.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_move()
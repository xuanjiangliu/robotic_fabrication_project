import rtde_receive # type: ignore
import rtde_control # <--- ADDED for Vision
import socket
import time
import struct

class URRobot:
    """
    Client: Monitors Robot State AND Controls Movement.
    1. Monitors State (rtde_receive)
    2. Sends Moves (rtde_control) - NEW
    3. Controls Freedrive (socket) - PRESERVED
    """
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.port_safety = 30002 
        self.rtde_r = None
        self.rtde_c = None # <--- ADDED
        self.connected = False

    def connect(self):
        print(f"[Monitor] Connecting to RTDE at {self.ip_address}...")
        try:
            # 1. Connect Receiver (Read-Only)
            self.rtde_r = rtde_receive.RTDEReceiveInterface(self.ip_address)
            
            # 2. Connect Control (Write/Move) - Protected in case robot is locked
            try:
                self.rtde_c = rtde_control.RTDEControlInterface(self.ip_address)
                print("✅ Control Interface (30004) Connected.")
            except Exception as e:
                print(f"⚠️ Control Interface Failed (Read-Only Mode): {e}")

            self.connected = True
            print("✅ Monitor Connected.")
            return True
        except Exception as e:
            print(f"❌ Connection Failed: {e}")
            self.connected = False
            return False

    def get_tcp_pose(self):
        """Returns [x, y, z, rx, ry, rz]"""
        if not self.connected or self.rtde_r is None:
            return None
        return self.rtde_r.getActualTCPPose()

    # --- NEW: Motion for Vision System ---
    def move_linear(self, pose, speed=0.25, accel=1.2):
        """
        Blocking linear move. Returns True if successful.
        Used by: pkg/skills/visual_harvest.py
        """
        if not self.rtde_c:
            print("❌ MOVE FAILED: No Control Interface.")
            return False
            
        try:
            # Check if we can move
            if not self.rtde_c.isProgramRunning():
                # If we are in Remote Control, this usually auto-starts.
                pass 

            print(f" -> Moving to: [{pose[0]:.3f}, {pose[1]:.3f}, {pose[2]:.3f}, ...]")
            success = self.rtde_c.moveL(pose, speed, accel)
            
            if not success:
                print(f"❌ ROBOT REJECTED MOVE. Check: Reach, Safety Stop, or Remote Mode.")
                return False
            return True
        except Exception as e:
            print(f"❌ Move Error: {e}")
            return False

    def stop(self):
        if self.rtde_c:
            self.rtde_c.stopL()

    # --- ORIGINAL: Freedrive & Sockets (PRESERVED) ---
    def enable_freedrive_translation_only(self):
        """
        Locks Orientation (Rx, Ry, Rz) but allows Translation (X, Y, Z).
        """
        print("[Monitor] Engaging TRANSLATION-ONLY Freedrive...")
        script = """
        def start_level_freedrive():
            freedrive_mode(p[0,0,0,0,0,0], [1,1,1,0,0,0])
            while (True):
                sync()
            end
        end
        """
        self._send_socket_command(script)
        self._send_socket_command("start_level_freedrive()\n")

    def stop_freedrive(self):
        """Exits freedrive mode."""
        print("[Monitor] Stopping Freedrive...")
        self._send_socket_command("end_freedrive_mode()\n")
        self._send_socket_command("stopj(2.0)\n")

    def disconnect(self):
        self.stop_freedrive()
        if self.rtde_r: 
            try: self.rtde_r.disconnect()
            except: pass
        if self.rtde_c: # <--- Clean up control too
            try: self.rtde_c.disconnect()
            except: pass
        self.connected = False

    def _send_socket_command(self, cmd_str):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect((self.ip_address, self.port_safety))
            s.sendall(cmd_str.encode('utf-8'))
            s.close()
        except Exception as e:
            print(f"[Monitor] Socket Send Error: {e}")

# --- RESTORED: URCapListener Class ---
class URCapListener:
    """
    Server: Handles the 'External Control' Handshake.
    Used by: pkg/drivers/robotiq_v2.py (Orchestrator Trigger)
    """
    def __init__(self, ip='0.0.0.0', port=50002):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.ip, self.port))
        self.sock.listen(1)
        self.client_conn = None
        self.addr = None
        print(f"[URCapListener] Listening on {self.ip}:{self.port}")

    def wait_for_connection(self):
        """Blocks until the robot connects."""
        print("[URCapListener] Waiting for robot handshake...")
        self.client_conn, self.addr = self.sock.accept()
        print(f"[URCapListener] Robot connected from {self.addr}")
        return True

    def send_move_script(self, target_pose, acc=0.5, vel=0.5):
        """
        Sends a movej() command to the robot.
        """
        if not self.client_conn:
            print("[Error] No robot connection.")
            return
        
        vals = [float(x) for x in target_pose] 
        a = float(acc)
        v = float(vel)

        script = (
            "def external_move():\n"
            "  movej(p[{0}, {1}, {2}, {3}, {4}, {5}], a={6}, v={7})\n"
            "end\n"
            "external_move()\n"
        ).format(vals[0], vals[1], vals[2], vals[3], vals[4], vals[5], a, v)

        print(f"[URCapListener] Sending Move: {script.strip()}")
        self.client_conn.send(script.encode('utf-8'))
        
        self.client_conn.close()
        self.client_conn = None
        print("[URCapListener] Script sent. Connection closed.")

    def close(self):
        if self.client_conn:
            self.client_conn.close()
        self.sock.close()
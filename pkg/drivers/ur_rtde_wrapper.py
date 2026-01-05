import rtde_receive
import rtde_control
import socket
import time
import struct

class URRobot:
    """
    Client: Monitors Robot State AND Controls Movement.
    1. Monitors State (rtde_receive)
    2. Sends Moves (rtde_control)
    3. Controls Freedrive (socket)
    4. Executes Atomic Transactions (sendCustomScript) - NEW
    """
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.port_safety = 30002 
        self.rtde_r = None
        self.rtde_c = None
        self.connected = False

    def connect(self):
        print(f"[Monitor] Connecting to RTDE at {self.ip_address}...")
        try:
            # 1. Connect Receiver (Read-Only)
            self.rtde_r = rtde_receive.RTDEReceiveInterface(self.ip_address)
            
            # 2. Connect Control (Write/Move)
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

    def move_linear(self, pose, speed=0.25, accel=1.2):
        """
        Blocking linear move. Returns True if successful.
        Used for Phase A/B (Non-critical moves).
        """
        if not self.rtde_c:
            print("❌ MOVE FAILED: No Control Interface.")
            return False
            
        try:
            if not self.rtde_c.isProgramRunning():
                # If remote control is active, this usually auto-starts.
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

    # --- NEW: Transactional Script Execution ---
    def execute_atomic_script(self, script_content):
        """
        Wraps a raw URScript in a function and sends it to the robot.
        Use this for critical sequences (Pick-and-Place) that cannot be interrupted.
        """
        if not self.rtde_c:
            print("❌ EXEC FAILED: No Control Interface.")
            return False

        print(f"[Atomic] Sending script transaction...")
        
        # We wrap the user content in a secondary function to ensure valid syntax
        # The 'def' keyword is required by the UR interpreter for function definitions.
        full_script = f"""
        def atomic_transaction():
            {script_content}
        end
        """
        
        try:
            # sendCustomScriptFunction sends the code to the robot's secondary interpreter.
            # It defines the function and effectively calls it.
            self.rtde_c.sendCustomScriptFunction("atomic_transaction", full_script)
            
            # Robust wait for completion:
            # 1. Wait for robot to acknowledge and start (program running becomes True)
            time.sleep(0.5) 
            
            # 2. Block while the robot is executing the script
            while self.rtde_c.isProgramRunning():
                time.sleep(0.1)
                
            print("✅ Atomic Transaction Complete.")
            return True
        except Exception as e:
            print(f"❌ Script Error: {e}")
            return False

    def stop(self):
        if self.rtde_c:
            self.rtde_c.stopL()

    # --- Freedrive & Sockets ---
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
        if self.rtde_c:
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

class URCapListener:
    """
    Server: Handles the 'External Control' Handshake.
    Legacy/Alternative method. Kept for compatibility.
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
        print("[URCapListener] Waiting for robot handshake...")
        self.client_conn, self.addr = self.sock.accept()
        print(f"[URCapListener] Robot connected from {self.addr}")
        return True

    def send_move_script(self, target_pose, acc=0.5, vel=0.5):
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
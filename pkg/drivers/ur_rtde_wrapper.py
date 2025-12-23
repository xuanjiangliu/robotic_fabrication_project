import socket
import time
import rtde_receive # type: ignore
from pkg.drivers import robotiq_preamble

class URRobot:
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.port = 30002
        self.rtde_r = None
        self.connected = False

    def connect(self):
        print(f"[UR7e] Connecting to {self.ip_address}...")
        try:
            self.rtde_r = rtde_receive.RTDEReceiveInterface(self.ip_address)
            self.connected = True
            
            # Send Modbus Activation
            print("[UR7e] Connected. Activating Gripper (Modbus)...")
            self._send_socket_command('textmsg("EVOFAB: Activating Modbus...")\n')
            self._send_socket_command(robotiq_preamble.get_activation_script())
            
            # Wait for physical activation
            time.sleep(3.5)
            return True
        except Exception as e:
            print(f"[UR7e] Connection Failed: {e}")
            self.connected = False
            return False

    # --- SENSORS ---
    def get_joint_angles(self):
        if self.rtde_r: return self.rtde_r.getActualQ()
        return None
    
    def get_tcp_pose(self):
        if self.rtde_r: return self.rtde_r.getActualTCPPose()
        return [0.0] * 6

    def is_moving(self):
        if self.rtde_r:
            try:
                return any(abs(s) > 0.01 for s in self.rtde_r.getActualQd())
            except:
                return False
        return False

    # --- MOTION ---
    def move_j(self, q, speed=1.05, acc=1.4):
        if not self.connected: return
        q_str = "[" + ",".join([f"{x:.4f}" for x in q]) + "]"
        self._send_socket_command(f"movej({q_str}, a={acc}, v={speed})\n")

    def move_l(self, p, speed=0.25, acc=0.5):
        if not self.connected: return
        p_str = "p[" + ",".join([f"{x:.5f}" for x in p]) + "]"
        self._send_socket_command(f"movel({p_str}, a={acc}, v={speed})\n")

    def stop(self):
        self._send_socket_command("stopj(2.0)\n")

    # --- GRIPPER ---
    def gripper_close(self):
        print("[UR7e] Gripper CLOSE (Modbus)...")
        self._send_socket_command(robotiq_preamble.get_move_script(255))

    def gripper_open(self):
        print("[UR7e] Gripper OPEN (Modbus)...")
        self._send_socket_command(robotiq_preamble.get_move_script(0))

    def disconnect(self):
        if self.rtde_r: self.rtde_r.disconnect()
        self.connected = False

    def _send_socket_command(self, cmd_str):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect((self.ip_address, self.port))
            s.sendall(cmd_str.encode('utf-8'))
            s.close()
        except Exception as e:
            print(f"[UR7e] Socket Send Error: {e}")
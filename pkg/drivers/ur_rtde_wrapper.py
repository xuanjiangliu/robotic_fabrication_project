import socket
import time
import rtde_receive # type: ignore
from src.drivers import robotiq_preamble

class URRobot:
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.port = 30002
        self.rtde_r = None
        self.connected = False

    def connect(self):
        print(f"[UR7e] Connecting to {self.ip_address}...")
        try:
            # 1. Connect RTDE
            self.rtde_r = rtde_receive.RTDEReceiveInterface(self.ip_address)
            
            # 2. Verify Socket
            self._send_socket_command('textmsg("RoboFab: Python Connected")\n')
            self.connected = True
            
            print("[UR7e] Connected. initializing Gripper via Modbus...")
            
            # 3. Send Activation Script
            script = robotiq_preamble.get_activation_script()
            self._send_socket_command(script)
            
            # Wait for "Click-Clack"
            time.sleep(3.0)
            
            return True
        except Exception as e:
            print(f"[UR7e] Connection Failed: {e}")
            self.connected = False
            return False

    # --- SENSORS ---
    def get_joint_angles(self):
        if self.rtde_r: return self.rtde_r.getActualQ()
        return None

    def get_joint_speeds(self):
        if self.rtde_r: return self.rtde_r.getActualQd()
        return [0.0] * 6 

    def get_tcp_pose(self):
        if self.rtde_r: return self.rtde_r.getActualTCPPose()
        return [0.0] * 6

    def is_moving(self):
        if self.rtde_r:
            try:
                speeds = self.rtde_r.getActualQd()
                return any(abs(s) > 0.01 for s in speeds)
            except Exception:
                return False
        return False

    # --- MOVEMENT ---
    def move_j(self, joint_configuration, speed=1.05, acceleration=1.4):
        if not self.connected: return
        q_str = "[" + ",".join([f"{x:.4f}" for x in joint_configuration]) + "]"
        command = f"movej({q_str}, a={acceleration}, v={speed})\n"
        self._send_socket_command(command)

    def move_l(self, pose, speed=0.25, acceleration=0.5):
        if not self.connected: return
        pose_str = "p[" + ",".join([f"{x:.5f}" for x in pose]) + "]"
        command = f"movel({pose_str}, a={acceleration}, v={speed})\n"
        self._send_socket_command(command)

    def stop(self):
        self._send_socket_command("stopj(2.0)\n")

    # --- GRIPPER ---
    def gripper_close(self):
        print("[UR7e] Gripper CLOSE...")
        self._send_socket_command(robotiq_preamble.get_move_script(255))

    def gripper_open(self):
        print("[UR7e] Gripper OPEN...")
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
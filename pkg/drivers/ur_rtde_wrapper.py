import rtde_receive # type: ignore
import socket
import time

class URRobot:
    """
    Telemetry Monitor & Safety Stop.
    Motion and Gripper logic are now handled by the Tablet Program.
    This class ensures we can see what's happening and STOP if needed.
    """
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.port_safety = 30002 # Primary Interface (best for stopping)
        self.rtde_r = None
        self.connected = False

    def connect(self):
        print(f"[Monitor] Connecting to RTDE at {self.ip_address}...")
        try:
            self.rtde_r = rtde_receive.RTDEReceiveInterface(self.ip_address)
            self.connected = True
            print("✅ Monitor Connected.")
            return True
        except Exception as e:
            print(f"❌ Connection Failed: {e}")
            self.connected = False
            return False

    def get_status(self):
        """Returns relevant dashboard data for your Orchestrator."""
        if not self.connected: return {}
        try:
            return {
                "joints": self.rtde_r.getActualQ(), # type: ignore
                "tcp": self.rtde_r.getActualTCPPose(), # type: ignore
                "safety_mode": self.rtde_r.getSafetyMode(), # type: ignore
                "robot_mode": self.rtde_r.getRobotMode(),   # type: ignore
                "is_moving": any(abs(v) > 0.01 for v in self.rtde_r.getActualQd()) # type: ignore
            }
        except:
            return {}

    def stop(self):
        """
        Emergency Stop.
        Sends 'stopj(2.0)' to Port 30002.
        This will effectively PAUSE/STOP the running Tablet Program.
        """
        print("[Monitor] Sending STOP command...")
        self._send_socket_command("stopj(2.0)\n")

    def disconnect(self):
        if self.rtde_r: 
            try:
                self.rtde_r.disconnect()
            except:
                pass
        self.connected = False

    def _send_socket_command(self, cmd_str):
        """Helper to send raw scripts to the Primary Interface."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect((self.ip_address, self.port_safety))
            s.sendall(cmd_str.encode('utf-8'))
            s.close()
        except Exception as e:
            print(f"[Monitor] Socket Send Error: {e}")
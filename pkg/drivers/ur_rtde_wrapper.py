import rtde_receive # type: ignore
import socket
import time

class URRobot:
    """
    Telemetry Monitor & Safety Stop.
    Now includes Remote Freedrive Control.
    """
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.port_safety = 30002 
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

    def get_tcp_pose(self):
        if not self.connected or self.rtde_r is None:
            return None
        return self.rtde_r.getActualTCPPose()

    def enable_freedrive_translation_only(self):
        """
        Locks Orientation (Rx, Ry, Rz) but allows Translation (X, Y, Z).
        Useful for keeping camera level while moving by hand.
        """
        print("[Monitor] Engaging TRANSLATION-ONLY Freedrive...")
        # freedrive_mode(frame, constraints)
        # constraints: [x, y, z, rx, ry, rz] -> 1=Free, 0=Fixed
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
        # Sending a stopj also helps kill the 'while' loop in the script above
        self._send_socket_command("stopj(2.0)\n")

    def disconnect(self):
        self.stop_freedrive()
        if self.rtde_r: 
            try:
                self.rtde_r.disconnect()
            except:
                pass
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
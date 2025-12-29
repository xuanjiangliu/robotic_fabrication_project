import rtde_io # type: ignore
import rtde_receive # type: ignore
import time

class RTDETriggerClient:
    """
    Manages the 'Handshake' with the Tablet Program via RTDE (Port 30004).
    Target: Input Integer Register 24.
    """
    def __init__(self, robot_ip):
        self.ip = robot_ip
        self.rtde_io = None
        self.rtde_r = None
        self.trigger_reg = 18 

    def connect(self):
        try:
            # rtde_io connects to Port 30004 (Control Interface)
            self.rtde_io = rtde_io.RTDEIOInterface(self.ip)
            # rtde_r connects to Port 30004 (Data Interface)
            self.rtde_r = rtde_receive.RTDEReceiveInterface(self.ip)
            return True
        except Exception as e:
            print(f"[Trigger] Connection Failed: {e}")
            return False

    def trigger_cycle(self):
        """
        Pulses Register 24 to '1' to break the 'Wait' loop on the tablet.
        """
        if not self.rtde_io:
            if not self.connect(): return False

        print(f"[Trigger] Activating Cycle (Reg {self.trigger_reg} -> 1)...")
        
        # 1. Set Register 24 to HIGH (Robot sees this and exits the While loop)
        self.rtde_io.setInputIntRegister(self.trigger_reg, 1) # type: ignore
        
        # 2. Wait briefly to ensure the robot catches the signal
        time.sleep(0.5)
        
        # 3. Reset Register 24 to LOW (So it waits again at the start of the next loop)
        self.rtde_io.setInputIntRegister(self.trigger_reg, 0) # type: ignore
        
        print("[Trigger] Signal Sent. Cycle Started.")
        return True

    def is_program_running(self):
        """Checks if the robot is actually executing a program (Safety Check)."""
        if self.rtde_r:
            # Bit 1 of Robot Status indicates 'Program Running'
            return self.rtde_r.getRobotStatus() & 1
        return False
        
    def disconnect(self):
        if self.rtde_io: self.rtde_io.disconnect()
        if self.rtde_r: self.rtde_r.disconnect()
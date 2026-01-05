import time
import cv2
import numpy as np
from pkg.vision.analysis import find_part_alignment
from pkg.vision.eye_in_hand import EyeInHand

# --- CONFIGURATION (METERS) ---
HEIGHT_SCAN_HIGH = 0.40  
HEIGHT_SCAN_LOW  = 0.20  
HEIGHT_PICK      = 0.015 
HEIGHT_SAFE      = 0.30  

class VisualHarvester:
    def __init__(self, robot_driver):
        self.bot = robot_driver
        self.vision = EyeInHand() 
        
        self.cap = cv2.VideoCapture(1, cv2.CAP_MSMF) 
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        # Standard Downward Orientation [Rx, Ry, Rz]
        # Verify this matches your 'get_tcp_pose()' orientation!
        self.default_orientation = [2.22, 2.22, 0.0] 

    def get_image(self):
        for _ in range(5): self.cap.read()
        ret, frame = self.cap.read()
        return frame

    def execute(self):
        print("--- Starting Stop-Look-Refine-Pick ---")

        # ==========================================
        # PHASE A: Coarse Scan (Python Control)
        # ==========================================
        print("[Phase A] Coarse Scan")
        img = self.get_image()
        u, v, _, found = find_part_alignment(img)
        
        if not found:
            print("❌ Phase A: No object seen.")
            return False

        curr_pose = self.bot.get_tcp_pose()
        if not curr_pose:
            print("❌ Robot disconnected.")
            return False

        tx, ty = self.vision.pixel_to_robot(u, v, curr_pose)
        print(f" -> Coarse Target: {tx:.3f}, {ty:.3f}")
        
        # Move to Hover
        print(f" -> Moving to Hover...")
        hover_pose = [tx, ty, HEIGHT_SCAN_LOW] + self.default_orientation
        
        # --- FIX: Check for Reachability/Safety Here ---
        if not self.bot.move_linear(hover_pose, speed=0.5):
            print("❌ Phase A: Move Failed (Reach/Safety). Aborting.")
            return False

        # ==========================================
        # PHASE B: Refine (Python Control)
        # ==========================================
        print("[Phase B] Refine Alignment")
        time.sleep(0.5) 
        img = self.get_image()
        u, v, angle, found = find_part_alignment(img)

        if not found:
            print("❌ Phase B: Object lost.")
            return False

        fine_pose = self.bot.get_tcp_pose()
        fx, fy = self.vision.pixel_to_robot(u, v, fine_pose)
        print(f" -> Fine Target: {fx:.3f}, {fy:.3f}")

        # ==========================================
        # PHASE C: Atomic Transaction (Robot Control)
        # ==========================================
        print("[Phase C] Atomic Pick Transaction")
        
        # The logic that was "deleted" is now here:
        script = f"""
            movel(p[{fx}, {fy}, {HEIGHT_SCAN_LOW}, {self.default_orientation[0]}, {self.default_orientation[1]}, {self.default_orientation[2]}], a=1.0, v=0.5)
            movel(p[{fx}, {fy}, {HEIGHT_PICK}, {self.default_orientation[0]}, {self.default_orientation[1]}, {self.default_orientation[2]}], a=0.5, v=0.1)
            set_digital_out(0, True)
            sleep(0.8)
            movel(p[{fx}, {fy}, {HEIGHT_SAFE}, {self.default_orientation[0]}, {self.default_orientation[1]}, {self.default_orientation[2]}], a=1.0, v=0.5)
        """
        
        return self.bot.execute_atomic_script(script)
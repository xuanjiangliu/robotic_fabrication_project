import time
import cv2
import numpy as np
from pkg.vision.analysis import find_part_alignment
from pkg.vision.eye_in_hand import EyeInHand

# --- CONFIGURATION (METERS) ---
# Update these slightly if your gripper is longer/shorter
HEIGHT_SCAN_HIGH = 0.40  # Phase A: Look from high up
HEIGHT_SCAN_LOW  = 0.20  # Phase B: Look closer for precision
HEIGHT_PICK      = 0.015 # Phase C: Height to Grip (Surface of bed approx)
HEIGHT_SAFE      = 0.30  # Height to retract to

class VisualHarvester:
    def __init__(self, robot_driver):
        self.bot = robot_driver
        self.vision = EyeInHand() # Loads your calibrated offsets
        
        # Open Camera
        self.cap = cv2.VideoCapture(1, cv2.CAP_MSMF) 
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        # Default Gripper Orientation (Pointing Down)
        # [Rx, Ry, Rz] in radians. 
        # Standard UR "Down" is often roughly [2.22, 2.22, 0.0] or [pi, 0, 0] depending on mount.
        # Use the values from your 'get_actual_tcp_pose()' if uncertain.
        self.default_orientation = [2.22, 2.22, 0.0] 

    def get_image(self):
        # Flush buffer to get a fresh frame
        for _ in range(5): self.cap.read()
        ret, frame = self.cap.read()
        return frame

    def execute(self):
        print("--- Starting Stop-Look-Refine-Pick ---")

        # ---------------------------------------------------------
        # PHASE A: Coarse Approach
        # ---------------------------------------------------------
        print("[Phase A] Coarse Scan (40cm)")
        # 1. Move Robot High? (Optional, assumes we are near home)
        # self.bot.move_linear([-0.15, -0.4, HEIGHT_SCAN_HIGH] + self.default_orientation)

        # 2. Look
        img = self.get_image()
        u, v, _, found = find_part_alignment(img)
        
        if not found:
            print("❌ Phase A: No Benchy seen.")
            return False

        # 3. Compute Coarse Target
        # Uses current robot pose to map pixels -> world
        curr_pose = self.bot.get_tcp_pose()
        tx, ty = self.vision.pixel_to_robot(u, v, curr_pose)
        
        print(f" -> Coarse Target: {tx:.3f}, {ty:.3f}")

        # ---------------------------------------------------------
        # PHASE B: Refine Hover
        # ---------------------------------------------------------
        print("[Phase B] Refine Hover (20cm)")
        # 1. Move directly above the target
        hover_pose = [tx, ty, HEIGHT_SCAN_LOW] + self.default_orientation
        self.bot.move_linear(hover_pose, speed=0.5) 
        
        # 2. Stop & Look (Implicit stop)
        time.sleep(0.5) # Let vibrations settle
        img = self.get_image()
        u, v, angle, found = find_part_alignment(img)

        if not found:
            print("❌ Phase B: Benchy lost!")
            return False

        # 3. Compute Fine Target
        final_x, final_y = self.vision.pixel_to_robot(u, v, self.bot.get_tcp_pose())
        
        # 4. Compute Angle
        # Note: 'angle' is the object's rotation in the image. 
        # You may need to ADD this to your base rotation or ignore it if using a suction cup.
        # For a parallel gripper, you want to align with this angle.
        print(f" -> Fine Target: {final_x:.3f}, {final_y:.3f}, Angle: {np.degrees(angle):.1f}")

        # ---------------------------------------------------------
        # PHASE C: Atomic Pick
        # ---------------------------------------------------------
        print("[Phase C] Atomic Pick")
        
        # Move Down
        self.bot.move_linear([final_x, final_y, HEIGHT_PICK] + self.default_orientation, speed=0.1)
        
        # GRIP (Placeholder print)
        print(" -> *GRIPPER CLOSE*") 
        time.sleep(1.0)
        
        # Retract
        self.bot.move_linear([final_x, final_y, HEIGHT_SAFE] + self.default_orientation, speed=0.5)
        
        print("✅ Harvest Complete")
        return True
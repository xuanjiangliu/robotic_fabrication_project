import json
import os
import numpy as np
import cv2
from scipy.spatial.transform import Rotation as R

class EyeInHand:
    def __init__(self, config_path="config/camera_offset.json"):
        self.matrix_cam2gripper = np.eye(4)
        self.load_calibration(config_path)
        
        # --- HARDWARE CONFIG ---
        # Pixels per Meter (PPM)
        # You should measure this at your standard height (e.g., Z=300mm)
        # For Gemini 335LG @ 300mm, it's roughly ~2000-3000.
        # Ideally, this should be dynamic based on Z, but fixed is fine for 2D picking.
        self.ppm = 2800.0 
        
        self.img_center_x = 640 # Half of 1280
        self.img_center_y = 360 # Half of 720

    def load_calibration(self, path):
        """Loads the Hand-Eye Calibration JSON."""
        if not os.path.exists(path):
            print(f"[EyeInHand] ⚠️ Calibration file {path} not found! Using Identity.")
            return

        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            # Construct 4x4 Homogeneous Matrix
            # T_cam_to_gripper
            mat = np.eye(4)
            mat[0, 3] = data["translation_x"]
            mat[1, 3] = data["translation_y"]
            mat[2, 3] = data["translation_z"]
            
            # Rotation
            rot_mat = np.array(data["rotation_matrix"])
            mat[:3, :3] = rot_mat
            
            self.matrix_cam2gripper = mat
            print(f"[EyeInHand] ✅ Loaded Offset: {mat[:3, 3]}")
            
        except Exception as e:
            print(f"[EyeInHand] ❌ Error loading calibration: {e}")

    def pixel_to_robot(self, u, v, robot_pose_vec):
        """
        Converts Pixel (u,v) -> Robot Base (x,y).
        robot_pose_vec: [x, y, z, rx, ry, rz]
        """
        # 1. Convert Pixel -> Camera Frame (Meters)
        # We assume the camera is looking 'down' Z-axis.
        # Image X+ usually aligns with Camera X+
        # Image Y+ usually aligns with Camera Y+
        x_cam = (u - self.img_center_x) / self.ppm
        y_cam = (v - self.img_center_y) / self.ppm 
        
        # Vector in Camera Frame (Assuming Z=0 plane relative to focus)
        # P_cam = [x, y, 0, 1]
        p_cam = np.array([x_cam, y_cam, 0.0, 1.0])
        
        # 2. Transform Camera -> Gripper (Using Calibration)
        p_gripper = self.matrix_cam2gripper @ p_cam
        
        # 3. Transform Gripper -> Base
        # Convert Robot Pose Vector to Matrix
        t_base = np.eye(4)
        t_base[:3, 3] = robot_pose_vec[:3]
        t_base[:3, :3] = R.from_rotvec(robot_pose_vec[3:6]).as_matrix()
        
        p_base = t_base @ p_gripper
        
        return p_base[0], p_base[1]
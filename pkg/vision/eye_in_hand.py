import json
import os
import numpy as np
import cv2
from scipy.spatial.transform import Rotation as R

class EyeInHand:
    def __init__(self, config_path="config/camera_offset.json"):
        self.matrix_cam2gripper = np.eye(4)
        
        # Default PPM (Hardware fallback if config missing)
        self.ppm = 2800.0 
        
        # Center of 1280x720
        self.img_center_x = 640 
        self.img_center_y = 360 

        # Load Calibration (Overwrites defaults)
        self.load_calibration(config_path)

    def load_calibration(self, path):
        """Loads the Hand-Eye Calibration JSON."""
        if not os.path.exists(path):
            print(f"[EyeInHand] ⚠️ Calibration file {path} not found! Using Defaults.")
            return

        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            # 1. Load Hand-Eye Matrix
            mat = np.eye(4)
            mat[0, 3] = data["translation_x"]
            mat[1, 3] = data["translation_y"]
            mat[2, 3] = data["translation_z"]
            
            rot_mat = np.array(data["rotation_matrix"])
            mat[:3, :3] = rot_mat
            
            self.matrix_cam2gripper = mat
            
            # 2. Load Scale (PPM)
            if "pixels_per_meter" in data:
                self.ppm = float(data["pixels_per_meter"])
                print(f"[EyeInHand] ✅ Loaded Scale: {self.ppm:.1f} PPM")
            else:
                print(f"[EyeInHand] ⚠️ 'pixels_per_meter' not in config. Using default {self.ppm}")

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
        x_cam = (u - self.img_center_x) / self.ppm
        y_cam = (v - self.img_center_y) / self.ppm 
        
        # Vector in Camera Frame (Assuming Z=0 plane relative to focus)
        p_cam = np.array([x_cam, y_cam, 0.0, 1.0])
        
        # 2. Transform Camera -> Gripper (Using Calibration)
        p_gripper = self.matrix_cam2gripper @ p_cam
        
        # 3. Transform Gripper -> Base
        t_base = np.eye(4)
        t_base[:3, 3] = robot_pose_vec[:3]
        t_base[:3, :3] = R.from_rotvec(robot_pose_vec[3:6]).as_matrix()
        
        p_base = t_base @ p_gripper
        
        return p_base[0], p_base[1]
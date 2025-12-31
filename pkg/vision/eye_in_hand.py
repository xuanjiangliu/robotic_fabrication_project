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
        
        # Center of 1280x720 (Update if using different resolution)
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
            mat[0, 3] = data.get("translation_x", 0.0)
            mat[1, 3] = data.get("translation_y", 0.0)
            mat[2, 3] = data.get("translation_z", 0.0)
            
            if "rotation_matrix" in data:
                rot_mat = np.array(data["rotation_matrix"])
                mat[:3, :3] = rot_mat
            
            self.matrix_cam2gripper = mat
            
            # 2. Load Scale (PPM)
            if "pixels_per_meter" in data:
                self.ppm = float(data["pixels_per_meter"])
            
            print(f"[EyeInHand] ✅ Loaded Calibration (Offset: {mat[:3, 3]})")
            
        except Exception as e:
            print(f"[EyeInHand] ❌ Error loading calibration: {e}")

    def pixel_to_robot(self, u, v, robot_pose_vec):
        """
        Converts Pixel (u,v) -> Robot Base (x,y).
        
        Args:
            u, v: Pixel coordinates from the camera.
            robot_pose_vec: The current robot pose [x, y, z, rx, ry, rz] (Observation Pose).
            
        Returns:
            (target_x, target_y) in Robot Base Frame.
        """
        # 1. Convert Pixel -> Camera Frame (Meters)
        # We assume the camera is looking 'down' Z-axis.
        # Note: Directions (neg/pos) depend on camera mounting. 
        # Usually: Right in Image (+u) = +x in Cam, Down in Image (+v) = +y in Cam.
        x_cam = (u - self.img_center_x) / self.ppm
        y_cam = (v - self.img_center_y) / self.ppm 
        
        # Vector in Camera Frame (Assuming Z=0 plane relative to focus)
        p_cam = np.array([x_cam, y_cam, 0.0, 1.0])
        
        # 2. Transform Camera -> Gripper (Using Calibration)
        p_gripper = self.matrix_cam2gripper @ p_cam
        
        # 3. Transform Gripper -> Base
        # We need to construct the transformation matrix of the Robot Flange relative to Base
        t_base = np.eye(4)
        t_base[:3, 3] = robot_pose_vec[:3]
        t_base[:3, :3] = R.from_rotvec(robot_pose_vec[3:6]).as_matrix()
        
        p_base = t_base @ p_gripper
        
        return p_base[0], p_base[1]
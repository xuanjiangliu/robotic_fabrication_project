import cv2
import numpy as np
import os
import time

class Camera:
    """
    Hardware Abstraction Layer (HAL) for the Orbbec Gemini 335L.
    Reverted to the MSMF/MJPG protocol verified in test_yolo_follow.py.
    """
    def __init__(self, camera_index=1):
        self.camera_index = camera_index
        self.cap = None
        self.depth_scale = 0.001 
        self.intrinsics = None

    def start(self):
        """
        Initializes the camera using MSMF and forces MJPG to avoid 
        Windows media format negotiation errors.
        """
        print(f"[Camera] Connecting to Camera {self.camera_index} via MSMF...")
        
        # Open with MSMF backend
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_MSMF)
        
        if not self.cap.isOpened():
            print(f"❌ [Camera] Error: Opening failed. Ensure Zadig drivers are reverted.")
            return False

        # Force MJPG codec and 720p resolution as verified in diagnostics
        try:
            fourcc = cv2.VideoWriter.fourcc(*'MJPG')
        except AttributeError:
            fourcc = cv2.VideoWriter_fourcc(*'MJPG') # type: ignore 
            
        self.cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        # Warmup sequence to clear initial buffers
        for _ in range(15):
            ret, _ = self.cap.read()
            if ret: break
            time.sleep(0.05)
        
        print("✅ [Camera] MSMF/MJPG Stream Ready.")
        return True

    def get_frames(self):
        """Returns BGR frame. Note: Depth is not natively supported in MSMF mode."""
        if self.cap is None: return None, None
        ret, frame = self.cap.read()
        # In this mode, we return the color frame for both slots
        return (frame, frame) if ret else (None, None)

    def stop(self):
        if self.cap: self.cap.release()

    def load_intrinsics(self, path):
        """Loads calibration from config/camera_offset.json."""
        if not os.path.exists(path):
            self.intrinsics = np.array([[900, 0, 640], [0, 900, 360], [0, 0, 1]])
            return self.intrinsics, None
        try:
            with open(path, 'r') as f:
                import json
                data = json.load(f)
                self.intrinsics = np.array(data.get("rotation_matrix", np.eye(3)))
                return self.intrinsics, None
        except Exception:
            return np.eye(3), None

    def get_depth_scale(self):
        return self.depth_scale
import cv2
import numpy as np

class ActuatorAnalyzer:
    """
    Deterministic vision for PneuNet characterization.
    Supports both real Depth Gating and Brightness Thresholding (MSMF Fallback).
    """
    def __init__(self, z_min=0.40, z_max=0.55, threshold=200):
        # Parameters for real 16-bit depth sensors
        self.z_min = z_min 
        self.z_max = z_max
        
        # Parameter for standard UVC/MSMF sensors (brightness threshold 0-255)
        self.threshold = threshold
        
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    def generate_mask(self, frame: np.ndarray, depth_scale: float = 0.001) -> np.ndarray:
        """
        Isolates the actuator by either depth-gating or brightness-thresholding.
        Automatically detects which mode to use based on the input range.
        """
        # 1. Pre-process: Ensure single channel
        if len(frame.shape) == 3:
            # If color frame is passed, convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        # 2. Logic Selection: Detect if input is Depth (mm) or Grayscale (0-255)
        # Real depth values for an actuator at 45cm are ~450. 
        # Grayscale values are usually < 255.
        if np.max(gray) > 255:
            # MODE A: REAL DEPTH GATING
            depth_meters = gray * depth_scale
            mask = cv2.inRange(depth_meters, self.z_min, self.z_max) # type: ignore
        else:
            # MODE B: BRIGHTNESS THRESHOLDING (MSMF Fallback)
            # Isolates the white PneuNet from the dark holder
            _, mask = cv2.threshold(gray, self.threshold, 255, cv2.THRESH_BINARY)

        # 3. Morphology: Clean noise and fill small gaps
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel)
        return mask

    def extract_spine(self, mask: np.ndarray) -> np.ndarray:
        """
        Uses thinning (skeletonization) to find the neutral bending axis.
        """
        # Requires opencv-contrib-python
        skeleton = cv2.ximgproc.thinning(mask)
        return skeleton
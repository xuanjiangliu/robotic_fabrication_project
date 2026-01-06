# pkg/vision/analyzer.py
import cv2
import numpy as np

class DepthGatedAnalyzer:
    """
    Deterministic vision for PneuNet characterization.
    """
    def __init__(self, z_min=0.40, z_max=0.55):
        # Configured based on the distance to your observation stand
        self.z_min = z_min 
        self.z_max = z_max
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    def generate_mask(self, depth_frame: np.ndarray, depth_scale: float) -> np.ndarray:
        """
        Isolates the actuator by clipping everything outside the Z-range.
        """
        depth_meters = depth_frame * depth_scale
        
        # Binary mask of objects at the correct distance
        mask = cv2.inRange(depth_meters, self.z_min, self.z_max)
        
        # Clean noise
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel)
        return mask

    def extract_spine(self, mask: np.ndarray) -> np.ndarray:
        """
        Uses thinning to find the neutral bending axis (spine).
        """
        # Requires opencv-contrib-python
        skeleton = cv2.ximgproc.thinning(mask)
        return skeleton
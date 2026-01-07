import cv2
import numpy as np
import logging
from .characterization_engine import BaseCharacterizationEngine, EngineState
from pkg.utils.geometry import compute_spine_curvature

class DeterministicEngine(BaseCharacterizationEngine):
    """
    Concrete implementation of the characterization engine using 
    deterministic vision (thresholding + skeletonization).
    """
    def __init__(self, camera_idx=1, pneu_port="COM5", ppm=1916.2, threshold=205):
        # Initialize the base class which sets up Camera and PneumaticSerial
        super().__init__(camera_idx=camera_idx, pneu_port=pneu_port, ppm=ppm)
        
        self.logger = logging.getLogger("RoboFab.DeterministicEngine")
        
        # Override analyzer with specific threshold if needed
        self.analyzer.threshold = threshold
        
        # ROI Configuration (normalized 0.0 to 1.0)
        self.roi_v = [0.35, 0.85]
        self.roi_h = [0.4, 0.60]

    def get_roi_mask(self, frame):
        """Generates a binary ROI mask for the current frame dimensions."""
        h, w = frame.shape[:2]
        y1, y2 = int(h * self.roi_v[0]), int(h * self.roi_v[1])
        x1, x2 = int(w * self.roi_h[0]), int(w * self.roi_h[1])
        
        roi_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.rectangle(roi_mask, (x1, y1), (x2, y2), 255, -1)
        return roi_mask, (x1, y1, x2, y2)

    def process_frame(self, frame):
        """
        Executes the deterministic vision pipeline:
        ROI -> Threshold -> Mask -> Skeleton -> Curvature.
        """
        # 1. Generate ROI and Mask
        roi_mask, _ = self.get_roi_mask(frame)
        binary_mask = self.analyzer.generate_mask(frame)
        
        # Apply ROI to the mask
        combined_mask = cv2.bitwise_and(binary_mask, roi_mask)
        
        # 2. Extract Spine Skeleton
        skeleton = self.analyzer.extract_spine(combined_mask)
        
        # 3. Compute Curvature (K)
        res = compute_spine_curvature(skeleton, self.ppm)
        
        # We store the latest mask and skeleton for HUD rendering
        self.last_mask = combined_mask
        self.last_skeleton = skeleton
        
        return res.mean_curvature

    def render_hud(self, frame, curvature):
        """
        Implements the Diagnostic HUD requirements:
        - Yellow ROI Box
        - Red Mask Overlay
        - Green Spine Skeleton
        """
        display = frame.copy()
        _, roi_coords = self.get_roi_mask(frame)
        x1, y1, x2, y2 = roi_coords
        
        # Draw UI Elements
        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 255), 2)  # Yellow ROI
        
        if hasattr(self, 'last_mask'):
            display[self.last_mask > 0] = [0, 0, 255] # Red Mask Overlay
            
        if hasattr(self, 'last_skeleton'):
            display[self.last_skeleton > 0] = [0, 255, 0] # Green Spine
            
        # Text Overlay
        color = (0, 255, 0) if self.state != EngineState.IDLE else (255, 255, 255)
        cv2.putText(display, f"STATE: {self.state.name}", (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.putText(display, f"K: {curvature:.4f} m^-1", (20, 90), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imshow("RoboFab: Characterization HUD", display)
        cv2.waitKey(1)
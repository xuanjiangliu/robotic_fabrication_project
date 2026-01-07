import cv2
import numpy as np
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pkg.vision.eye_in_hand import EyeInHand
from pkg.vision.analyzer import DepthGatedAnalyzer

def main():
    print("--- Diagnostic: Depth-Gated Vision & Skeleton ---")
    
    # Initialize hardware and analyzer
    cam = Camera()
    if not cam.start(): return
    
    # Configured for a testing stand approx 45cm away
    analyzer = DepthGatedAnalyzer(z_min=0.40, z_max=0.50)
    
    print("Instructions: Place PneuNet 45cm from camera. Press 'q' to quit.")
    
    try:
        while True:
            depth_frame, color_image = cam.get_frames()
            if color_image is None: continue
            
            # 1. Generate Mask via Depth Gating
            mask = analyzer.generate_mask(
                np.asanyarray(depth_frame.get_data()), 
                cam.get_depth_scale()
            )
            
            # 2. Extract Spine (Skeleton)
            skeleton = analyzer.extract_spine(mask)
            
            # 3. Visualization
            display = color_image.copy()
            # Overlay mask in red
            display[mask > 0] = [0, 0, 255]
            # Overlay skeleton in bright green
            display[skeleton > 0] = [0, 255, 0]
            
            cv2.imshow("Deterministic Vision Test", display)
            if cv2.waitKey(1) & 0xFF == ord('q'): break
    finally:
        cam.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
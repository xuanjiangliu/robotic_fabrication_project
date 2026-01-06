import numpy as np
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pkg.camera import Camera
from pkg.vision.analyzer import DepthGatedAnalyzer
from pkg.utils.geometry import compute_spine_curvature

def main():
    print("--- Diagnostic: Spine Curvature Calculation ---")
    
    cam = Camera()
    if not cam.start(): return
    
    analyzer = DepthGatedAnalyzer(z_min=0.40, z_max=0.50)
    intrinsics, _ = cam.load_intrinsics("ml/configs/calibration_data.npz")
    
    try:
        while True:
            depth_obj, _ = cam.get_frames()
            if depth_obj is None: continue
            
            depth_array = np.asanyarray(depth_obj.get_data())
            mask = analyzer.generate_mask(depth_array, cam.get_depth_scale())
            skeleton = analyzer.extract_spine(mask)
            
            # Calculate 3D Curvature from the Spine
            results = compute_spine_curvature(
                skeleton, depth_array, intrinsics, cam.get_depth_scale()
            )
            
            print(f"Curvature -> Mean: {results.mean_curvature:.4f} | Max: {results.max_curvature:.4f}", end='\r')
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        cam.stop()

if __name__ == "__main__":
    main()
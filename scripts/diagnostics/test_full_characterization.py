import sys
import os
import time
import logging
import yaml
import numpy as np
import cv2

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pkg.drivers.ur_rtde_wrapper import URRobot
from pkg.drivers.pneumatic_serial import PneumaticSerial
from pkg.utils.geometry import compute_spine_curvature
# Assuming your camera wrapper is in pkg/vision/eye_in_hand.py or similar
from pkg.vision.eye_in_hand import EyeInHand

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - [Test] - %(message)s')
    
    # 1. Load your specific configuration
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../config/cell_config_example.yaml'))
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # 2. Hardware Initialization
    logging.info("Initializing Hardware...")
    cam = EyeInHand() 
    
    # Use configurable COM port from YAML
    pneumatics = PneumaticSerial(port=config['pneumatics']['port'])
    
    # Robot Control using IPs from YAML
    robot = URRobot(config['network']['robot_ip'])
    
    # Analyzer using Z-clipping from YAML
    analyzer = DepthGatedAnalyzer(
        z_min=config['characterization']['z_min'],
        z_max=config['characterization']['z_max']
    )

    # Load intrinsics for 3D back-projection
    calib_path = os.path.join("../../ml/configs/calibration_data.npz")
    # Placeholder for intrinsics loading logic
    intrinsics = np.array([[600, 0, 320], [0, 600, 240], [0, 0, 1]]) 

    # 3. Movement to Testing Pose
    # Uses the 'home' waypoint from your YAML as a safe starting point
    test_pose = config['waypoints'].get('home')
    logging.info(f"Moving to Testing Pose: {test_pose}")
    robot.move_to_pose(test_pose)

    # 4. Asynchronous Inflation & Vision Loop
    duration = config['pneumatics']['default_duration_ms'] # 2500ms pulse
    logging.info(f"Starting {duration}ms pulse on Channel 1...")
    
    pneumatics.start_pulse(1, duration)
    
    data_points = []
    try:
        while pneumatics.is_busy():
            # Replace with your actual camera frame acquisition logic
            color_img = np.zeros((480, 640, 3), dtype=np.uint8)
            depth_map = np.zeros((480, 640), dtype=np.uint16) 

            # Deterministic Vision Processing
            mask = analyzer.generate_mask(depth_map, 0.001) # 0.001 depth scale
            skeleton = analyzer.extract_spine(mask)

            # Curvature Analysis (60 deg tilt)
            result = compute_spine_curvature(
                skeleton, depth_map, intrinsics, 
                0.001, 
                base_angle_deg=config['characterization']['base_angle_deg']
            )

            if result.max_curvature > 0:
                data_points.append({
                    "time": time.time(),
                    "max_k": result.max_curvature
                })
                logging.info(f"Live Max Curvature: {result.max_curvature:.4f}")

    finally:
        logging.info(f"Captured {len(data_points)} samples during 2500ms inflation.")
        pneumatics.close()

if __name__ == "__main__":
    main()
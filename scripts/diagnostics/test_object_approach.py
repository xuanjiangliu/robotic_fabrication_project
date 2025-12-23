import sys
import os
import time
import cv2
import numpy as np
import math
from scipy.spatial.transform import Rotation as R
from ultralytics import YOLO # type: ignore

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pkg.drivers.ur_rtde_wrapper import URRobot
from pkg.utils.spatial import SpatialManager
from pkg.vision.eye_in_hand import EyeInHand

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
CAMERA_INDEX = 1

# Detection Settings (tuned for Benchy)
CONFIDENCE_THRESHOLD = 0.25 
STABILITY_TIME = 2.0        
IGNORE_CLASSES = [0]        # Ignore People
MIN_AREA_PX = 400           # Detect small objects
MAX_AREA_PX = 150000 

# --- MOTION SETTINGS ---
INSPECTION_HEIGHT = 0.08    # Low Z (8cm above floor)
TILT_ANGLE_DEG = 25.0       # Tilt 25 degrees to look

def init_camera():
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG')) # type: ignore
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    return cap

def calculate_inspection_pose(current_pose_vec, target_xyz, tilt_deg):
    """
    Calculates a target pose that is at target_xyz but TILTED relative to current tool.
    """
    r_curr = R.from_rotvec(current_pose_vec[3:])
    mat_curr = r_curr.as_matrix()

    # Tilt around Tool X (Pitch)
    r_rel = R.from_euler('x', tilt_deg, degrees=True) 
    mat_rel = r_rel.as_matrix()

    mat_new = mat_curr @ mat_rel
    r_new = R.from_matrix(mat_new)
    rot_vec_new = r_new.as_rotvec()

    return list(target_xyz) + list(rot_vec_new)

def main():
    print("--- RoboFab Automatic Inspection (Benchy Mode) ---")
    
    bot = URRobot(ROBOT_IP)
    spatial = SpatialManager()
    eye = EyeInHand()
    model = YOLO('yolov8n.pt') 
    
    if not bot.connect(): return
    if not spatial.cage_active: return

    cap = init_camera()
    if not cap.isOpened(): return

    entry_pose = spatial.get_entry_pose()
    if entry_pose is None: return

    print("✅ Moving to SEARCH POSE...")
    bot.move_l(entry_pose, speed=0.25)
    while bot.is_moving(): time.sleep(0.1)

    state = "SEARCHING"
    detection_start_time = None
    target_inspect_pose = None

    try:
        while True:
            ret, frame = cap.read()
            if not ret: break
            
            results = model(frame, verbose=False, conf=CONFIDENCE_THRESHOLD)
            
            valid_detections = []
            
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    area = (x2 - x1) * (y2 - y1)
                    
                    # Simple Filter: No People, correct size
                    if cls_id not in IGNORE_CLASSES and MIN_AREA_PX < area < MAX_AREA_PX:
                        valid_detections.append((box, area, cls_id))
            
            # Sort by largest area
            valid_detections.sort(key=lambda x: x[1], reverse=True)
            
            # --- STATE MACHINE ---
            if state == "SEARCHING":
                current_pose = bot.get_tcp_pose()
                
                if len(valid_detections) > 0:
                    target_box, _, cls_id = valid_detections[0]
                    name = model.names[cls_id]
                    
                    # Visualization
                    x1, y1, x2, y2 = target_box.xyxy[0].cpu().numpy()
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    cv2.putText(frame, f"{name}", (int(x1), int(y1)-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

                    if detection_start_time is None: detection_start_time = time.time()
                    elapsed = time.time() - detection_start_time
                    cv2.putText(frame, f"Lock: {elapsed:.1f}/{STABILITY_TIME}s", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

                    if elapsed >= STABILITY_TIME:
                        print(f"\n🔒 Locked on {name}! Calculating Swoop Path...")
                        
                        box_data = target_box.xywh[0].cpu().numpy()
                        r_x, r_y = eye.pixel_to_robot(box_data[0], box_data[1], current_pose)
                        
                        safe_floor_z = spatial.cage['z'][0]
                        target_z = safe_floor_z + INSPECTION_HEIGHT
                        
                        # Clamp and Calculate Tilted Pose
                        safe_xyz = spatial.clamp_target(current_pose, [r_x-current_pose[0], r_y-current_pose[1], target_z-current_pose[2]])
                        target_inspect_pose = calculate_inspection_pose(current_pose, safe_xyz, tilt_deg=TILT_ANGLE_DEG)
                        
                        state = "INSPECTING"
                else:
                    detection_start_time = None
                    cv2.putText(frame, "SCANNING...", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            elif state == "INSPECTING":
                print("\n🚀 Swooping to Inspect...")
                # Smooth interpolated move (Position + Tilt)
                bot.move_l(target_inspect_pose, speed=0.12, acceleration=0.2)
                while bot.is_moving(): time.sleep(0.1)
                
                print("📸 View Captured.")
                time.sleep(2.0) 
                state = "HOLDING"

            elif state == "HOLDING":
                cv2.putText(frame, "HOLDING - REMOVE OBJECT", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 255), 2)
                if len(valid_detections) == 0:
                    print("\n🧹 Object Removed. Retreating...")
                    time.sleep(0.5)
                    bot.move_l(entry_pose, speed=0.25)
                    while bot.is_moving(): time.sleep(0.1)
                    state = "SEARCHING"
                    detection_start_time = None

            cv2.imshow("RoboFab Automatic", frame)
            if cv2.waitKey(1) == ord('q'): break

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        bot.stop()
        bot.disconnect()
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
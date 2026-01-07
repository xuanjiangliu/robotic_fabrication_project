import sys
import os
import time
import json
import cv2
import numpy as np
from scipy.spatial.transform import Rotation as R

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from pkg.drivers.ur_rtde_wrapper import URRobot
from pkg.drivers.camera import Camera

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
CHECKERBOARD_DIMS = (8, 7)  
SQUARE_SIZE = 0.015         
SAVE_FILE = "config/camera_offset.json"
AUTO_CAPTURE_INTERVAL = 2.0 

def main():
    print("--- RoboFab Manual Calibration (MSMF Mode) ---")
    
    # 1. Start Camera First to stabilize system load
    cam = Camera(camera_index=1)
    if not cam.start(): return
    
    time.sleep(2.0) 

    # 2. Start Robot Listener
    bot = URRobot(ROBOT_IP)
    if not bot.connect():
        cam.stop()
        return

    R_gripper2base, t_gripper2base = [], [] 
    R_target2cam, t_target2cam = [], []   
    sample_count = 0
    last_capture_time = time.time()
    
    print("\n" + "="*60)
    print("👉 MANUAL MOVEMENT + AUTOCAPTURE")
    print("1. Move robot manually. Hold board steady for 2s.")
    print("2. Green bar = Autocapture imminent.")
    print("3. Press 'c' to force capture, 'q' to save.")
    print("="*60 + "\n")

    try:
        while True:
            _, frame = cam.get_frames()
            if frame is None: continue
            
            display_frame = frame.copy()
            current_time = time.time()
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found, corners = cv2.findChessboardCorners(gray, CHECKERBOARD_DIMS, None)

            if found:
                cv2.drawChessboardCorners(display_frame, CHECKERBOARD_DIMS, corners, found)
                progress = min((current_time - last_capture_time) / AUTO_CAPTURE_INTERVAL, 1.0)
                cv2.rectangle(display_frame, (0, 710), (int(1280 * progress), 720), (0, 255, 0), -1)
            else:
                last_capture_time = current_time

            cv2.imshow("Calibration View", display_frame)
            key = cv2.waitKey(1) & 0xFF

            # Capture Logic
            if (found and (current_time - last_capture_time) > AUTO_CAPTURE_INTERVAL) or (key == ord('c') and found):
                tcp_pose = bot.get_tcp_pose() #
                if tcp_pose:
                    objp = np.zeros((CHECKERBOARD_DIMS[0] * CHECKERBOARD_DIMS[1], 3), np.float32)
                    objp[:, :2] = np.mgrid[0:CHECKERBOARD_DIMS[0], 0:CHECKERBOARD_DIMS[1]].T.reshape(-1, 2) * SQUARE_SIZE
                    success, rvec, tvec = cv2.solvePnP(objp, corners, np.eye(3), None) # type: ignore
                    
                    if success:
                        R_gripper2base.append(R.from_rotvec(tcp_pose[3:6]).as_matrix())
                        t_gripper2base.append(np.array(tcp_pose[0:3]).reshape(3, 1))
                        R_target2cam.append(cv2.Rodrigues(rvec)[0])
                        t_target2cam.append(tvec)
                        sample_count += 1
                        print(f"✅ Sample {sample_count} Saved.")
                        last_capture_time = current_time
                        cv2.rectangle(display_frame, (0,0), (1280,720), (0,255,0), 20)
                        cv2.imshow("Calibration View", display_frame)
                        cv2.waitKey(300)

            if key == ord('q'): break
                
    finally:
        if sample_count >= 5:
            R_c2g, t_c2g = cv2.calibrateHandEye(R_gripper2base, t_gripper2base, R_target2cam, t_target2cam)
            with open(SAVE_FILE, 'w') as f:
                json.dump({
                    "translation_x": float(t_c2g[0][0]), 
                    "translation_y": float(t_c2g[1][0]), 
                    "translation_z": float(t_c2g[2][0]), 
                    "rotation_matrix": R_c2g.tolist()
                }, f, indent=4)
            print(f"💾 Calibration saved to {SAVE_FILE}")
        
        bot.disconnect()
        cam.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
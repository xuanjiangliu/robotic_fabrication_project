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

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
CAMERA_INDEX = 1
CHECKERBOARD_DIMS = (8, 7)
SQUARE_SIZE = 0.015         # 15mm
CALIB_FILE = "config/camera_offset.json"

def load_calibration(path):
    if not os.path.exists(path):
        print(f"❌ Calibration file {path} not found!")
        sys.exit(1)
    with open(path, 'r') as f:
        data = json.load(f)
    
    t_cg = np.eye(4)
    t_cg[:3, :3] = np.array(data["rotation_matrix"])
    t_cg[0, 3] = data["translation_x"]
    t_cg[1, 3] = data["translation_y"]
    t_cg[2, 3] = data["translation_z"]
    return t_cg

def draw_axis(img, corners, imgpts):
    corner = tuple(corners[0].ravel().astype(int))
    img = cv2.line(img, corner, tuple(imgpts[0].ravel().astype(int)), (0,0,255), 3) # X
    img = cv2.line(img, corner, tuple(imgpts[1].ravel().astype(int)), (0,255,0), 3) # Y
    img = cv2.line(img, corner, tuple(imgpts[2].ravel().astype(int)), (255,0,0), 3) # Z
    return img

def main():
    print("--- Calibration Accuracy Test (Level Mode) ---")
    
    T_cam_gripper = load_calibration(CALIB_FILE)
    
    bot = URRobot(ROBOT_IP)
    if not bot.connect(): return

    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)
    try:
        fourcc = cv2.VideoWriter.fourcc(*'MJPG') # type: ignore
    except AttributeError:
        fourcc = cv2.VideoWriter_fourcc(*'MJPG') # type: ignore
    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    axis_points = [[3*SQUARE_SIZE, 0, 0], [0, 3*SQUARE_SIZE, 0], [0, 0, -3*SQUARE_SIZE]]
    axis = np.array(axis_points, dtype=np.float32).reshape(-1, 3)
    
    # --- STEP 1: ORIENTATION SETUP ---
    print("\n" + "="*60)
    print("--- STEP 1: LEVEL THE CAMERA ---")
    print("1. Use the Tablet/FreeDrive to rotate the wrist.")
    print("2. Ensure the Camera is POINTING FORWARD and LEVEL.")
    print("3. When ready, press ENTER.")
    print("   (The robot will then LOCK rotation, allowing only X/Y/Z movement)")
    print("="*60 + "\n")
    input("👉 Press ENTER to LOCK ORIENTATION and START...")

    # Engage Restricted Freedrive
    bot.enable_freedrive_translation_only()
    print("🔒 ROTATION LOCKED. You can now move X/Y/Z freely.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret: continue
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found, corners = cv2.findChessboardCorners(gray, CHECKERBOARD_DIMS, None)
            
            if found:
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
                
                tcp_pose = bot.get_tcp_pose()
                if tcp_pose:
                    objp = np.zeros((CHECKERBOARD_DIMS[0] * CHECKERBOARD_DIMS[1], 3), np.float32)
                    objp[:, :2] = np.mgrid[0:CHECKERBOARD_DIMS[0], 0:CHECKERBOARD_DIMS[1]].T.reshape(-1, 2)
                    objp = objp * SQUARE_SIZE
                    
                    success, rvec, tvec = cv2.solvePnP(objp, corners, np.eye(3), None) # type: ignore
                    
                    if success:
                        # Calculations
                        dist_euclidean = np.linalg.norm(tvec)
                        dist_z = tvec[2][0] # Depth only
                        
                        imgpts, jac = cv2.projectPoints(axis, rvec, tvec, np.eye(3), None) # type: ignore
                        frame = draw_axis(frame, corners, imgpts)
                        
                        # Display
                        cv2.putText(frame, f"Real Dist: {dist_euclidean*1000:.1f} mm", (30, 50), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                        cv2.putText(frame, f"Z-Depth:   {dist_z*1000:.1f} mm", (30, 90), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                        
            cv2.imshow("Calibration Test", frame)
            if (cv2.waitKey(1) & 0xFF) == ord('q'):
                break
                
    except KeyboardInterrupt:
        pass
    
    print("\nStopping...")
    bot.stop_freedrive() # CRITICAL: Release the lock
    bot.disconnect()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
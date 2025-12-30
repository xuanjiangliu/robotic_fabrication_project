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
CAMERA_INDEX = 1            # Orbbec RGB
CHECKERBOARD_DIMS = (8, 7)  # Internal Corners
SQUARE_SIZE = 0.015         # 15mm
SAVE_FILE = "config/camera_offset.json"

# Auto-Capture Settings
AUTO_CAPTURE_INTERVAL = 2.0 # Seconds between captures
MIN_SAMPLES = 15            # Recommend more samples for auto mode

def init_camera():
    print(f"[Vision] Opening Camera Index {CAMERA_INDEX} (MSMF Backend)...")
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)
    if not cap.isOpened(): return None

    try:
        fourcc = cv2.VideoWriter.fourcc(*'MJPG') # type: ignore
    except AttributeError:
        fourcc = cv2.VideoWriter_fourcc(*'MJPG') # type: ignore

    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    # Warmup
    for _ in range(10):
        cap.read()
        time.sleep(0.05)
    return cap

def calculate_ppm(corners, dims):
    try:
        grid = corners.reshape((dims[1], dims[0], 2)) 
        distances = []
        for r in range(dims[1]):
            for c in range(dims[0] - 1):
                distances.append(np.linalg.norm(grid[r, c] - grid[r, c+1]))
        for r in range(dims[1] - 1):
            for c in range(dims[0]):
                distances.append(np.linalg.norm(grid[r, c] - grid[r+1, c]))
        return np.mean(distances) / SQUARE_SIZE
    except:
        return None

def main():
    print("--- RoboFab Auto-Calibration ---")
    
    bot = URRobot(ROBOT_IP)
    if not bot.connect(): return

    cap = init_camera()
    if cap is None: return

    # Data Storage
    R_gripper2base = [] 
    t_gripper2base = [] 
    R_target2cam = []   
    t_target2cam = []   
    collected_ppms = [] 

    print("\n" + "="*60)
    print(f"--- AUTO CAPTURE MODE ({AUTO_CAPTURE_INTERVAL}s) ---")
    print("1. Target: Checkerboard (8, 7)")
    print("2. CRITICAL: You MUST Rotate the Tool (Pitch/Roll)!")
    print("   If you only move X/Y/Z, calibration WILL FAIL.")
    print("3. Hold robot steady when the timer hits.")
    print("4. Wait for the GREEN FLASH before moving.")
    print("5. Press 'q' to Finish.")
    print("="*60 + "\n")

    sample_count = 0
    last_capture_time = time.time()
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.5); continue
            
            display_frame = frame.copy()
            current_time = time.time()
            time_since_last = current_time - last_capture_time
            
            # 1. Detect Board
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found, corners = cv2.findChessboardCorners(gray, CHECKERBOARD_DIMS, None)

            # 2. UI Feedback
            if found:
                cv2.drawChessboardCorners(display_frame, CHECKERBOARD_DIMS, corners, found)
                
                # Timer Bar
                progress = min(time_since_last / AUTO_CAPTURE_INTERVAL, 1.0)
                bar_width = int(1280 * progress)
                color = (0, 255, 255) if progress < 1.0 else (0, 255, 0)
                cv2.rectangle(display_frame, (0, 710), (bar_width, 720), color, -1)
            
            cv2.putText(display_frame, f"Samples: {sample_count}", (30, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(display_frame, "Press 'q' to Finish", (30, 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

            # 3. Auto Capture Logic
            if found and time_since_last > AUTO_CAPTURE_INTERVAL:
                # Get Pose (Check connection)
                tcp_pose = bot.get_tcp_pose()
                
                if tcp_pose is None:
                    print("⚠️ Robot disconnected. Reconnecting...")
                    bot.connect()
                    last_capture_time = current_time + 1.0 # Add delay
                else:
                    # Refine & Solve
                    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                    corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
                    
                    objp = np.zeros((CHECKERBOARD_DIMS[0] * CHECKERBOARD_DIMS[1], 3), np.float32)
                    objp[:, :2] = np.mgrid[0:CHECKERBOARD_DIMS[0], 0:CHECKERBOARD_DIMS[1]].T.reshape(-1, 2)
                    objp = objp * SQUARE_SIZE

                    success, rvec, tvec = cv2.solvePnP(objp, corners, np.eye(3), None) # type: ignore
                    
                    if success:
                        # Save Data
                        R_gripper2base.append(R.from_rotvec(tcp_pose[3:6]).as_matrix())
                        t_gripper2base.append(np.array(tcp_pose[0:3]).reshape(3, 1))
                        
                        r_cam, _ = cv2.Rodrigues(rvec)
                        R_target2cam.append(r_cam)
                        t_target2cam.append(tvec)
                        
                        sample_ppm = calculate_ppm(corners, CHECKERBOARD_DIMS)
                        if sample_ppm: collected_ppms.append(sample_ppm)
                        
                        sample_count += 1
                        print(f"✅ Sample {sample_count} Captured! (Z: {tcp_pose[2]:.3f})")
                        
                        # Reset Timer
                        last_capture_time = current_time
                        
                        # Visual Flash (Green Screen)
                        cv2.rectangle(display_frame, (0,0), (1280,720), (0,255,0), 20)
                        cv2.imshow("Calibration View", display_frame)
                        cv2.waitKey(200) # Small pause to see the flash

            cv2.imshow("Calibration View", display_frame)
            if (cv2.waitKey(1) & 0xFF) == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\nAborted.")

    # --- CALCULATION ---
    if sample_count < 5:
        print(f"❌ Not enough samples ({sample_count}). Aborted.")
    else:
        print("\nComputing Calibration (Tsai)...")
        try:
            R_cam2gripper, t_cam2gripper = cv2.calibrateHandEye(
                R_gripper2base, t_gripper2base,
                R_target2cam, t_target2cam,
                method=cv2.CALIB_HAND_EYE_TSAI
            )
            
            final_ppm = np.mean(collected_ppms) if collected_ppms else 2800.0

            # Sanity Check for Translation (Roughly < 1.0m)
            if np.linalg.norm(t_cam2gripper) > 1.0:
                print("⚠️ WARNING: Large offset detected. Did you rotate the gripper enough?")

            print(f"✅ SUCCESS! Scale: {final_ppm:.2f} PPM")
            print(f"Offset: {t_cam2gripper.T}")

            output_data = {
                "translation_x": float(t_cam2gripper[0][0]),
                "translation_y": float(t_cam2gripper[1][0]),
                "translation_z": float(t_cam2gripper[2][0]),
                "rotation_matrix": R_cam2gripper.tolist(),
                "pixels_per_meter": float(final_ppm),
                "mm_per_pixel": float(1000.0/final_ppm)
            }
            
            os.makedirs("config", exist_ok=True)
            with open(SAVE_FILE, 'w') as f:
                json.dump(output_data, f, indent=4)
            print(f"💾 Saved to: {SAVE_FILE}")

        except Exception as e:
            print(f"❌ Error: {e}")

    bot.disconnect()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
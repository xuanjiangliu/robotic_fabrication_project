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
CAMERA_INDEX = 1            # Known working index (Orbbec RGB)
CHECKERBOARD_DIMS = (8, 7)  # Internal Corners (Columns, Rows). Count squares and subtract 1.
SQUARE_SIZE = 0.025         # Square side length in Meters (25mm)
SAVE_FILE = "config/camera_offset.json"

def init_camera():
    """
    Initializes the Orbbec Gemini camera with specific settings
    to prevent MSMF/DirectShow crashes on Windows.
    """
    print(f"[Vision] Opening Camera Index {CAMERA_INDEX} (MSMF Backend)...")
    
    # Use MSMF backend (Standard for Windows 10/11)
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)
    
    if not cap.isOpened():
        print(f"[Vision] ❌ Failed to open Camera {CAMERA_INDEX}.")
        return None

    # CRITICAL: Force MJPG to prevent "Assertion failed" / "Codec not found" crashes
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))  # type: ignore
    
    # Set Native Resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    # Warmup: Read a few frames to stabilize auto-exposure
    print("[Vision] Warming up sensor...")
    for _ in range(10):
        cap.read()
        time.sleep(0.05)
        
    print(f"[Vision] ✅ Camera Initialized ({int(cap.get(3))}x{int(cap.get(4))})")
    return cap

def main():
    print("--- RoboFab Hand-Eye Calibration ---")
    
    # 1. Connect Robot
    bot = URRobot(ROBOT_IP)
    if not bot.connect():
        print("❌ Robot Connection Failed")
        return

    # 2. Connect Camera
    cap = init_camera()
    if cap is None:
        return

    # Data Storage
    R_gripper2base = [] # Robot Rotation (Matrix)
    t_gripper2base = [] # Robot Translation (Vector)
    R_target2cam = []   # Camera Rotation (Matrix)
    t_target2cam = []   # Camera Translation (Vector)

    print("\n" + "="*50)
    print("--- INSTRUCTIONS ---")
    print(f"1. Target: Checkerboard with {CHECKERBOARD_DIMS} internal corners.")
    print("2. Move the robot to view the board from different angles.")
    print("   -> IMPORTANT: Vary the Angle (Pitch/Roll), not just X/Y position.")
    print("   -> IMPORTANT: Keep the board entirely inside the frame.")
    print("3. Press 'c' to Capture a sample.")
    print("4. Press 'q' to Finish and Calibrate.")
    print("="*50 + "\n")

    sample_count = 0
    
    try:
        while True:
            # Get Frame
            ret, frame = cap.read()
            if not ret or frame is None:
                print("⚠️ Lost video stream. Retrying...")
                time.sleep(0.5)
                continue
            
            display_frame = frame.copy()
            
            # Draw UI
            cv2.putText(display_frame, f"Samples: {sample_count}", (30, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(display_frame, "'c': Capture | 'q': Finish", (30, 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            cv2.imshow("Calibration View", display_frame)
            key = cv2.waitKey(1) & 0xFF

            # --- CAPTURE COMMAND ---
            if key == ord('c'):
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                found, corners = cv2.findChessboardCorners(gray, CHECKERBOARD_DIMS, None)
                
                if found:
                    # 1. Refine Corner Locations (Subpixel Accuracy)
                    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                    corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
                    
                    # 2. Get Robot Pose [x,y,z,rx,ry,rz]
                    tcp_pose = bot.get_tcp_pose()
                    
                    # 3. Solve Perspective-n-Point (PnP)
                    # Create object points: (0,0,0), (1,0,0), ... based on square size
                    objp = np.zeros((CHECKERBOARD_DIMS[0] * CHECKERBOARD_DIMS[1], 3), np.float32)
                    objp[:, :2] = np.mgrid[0:CHECKERBOARD_DIMS[0], 0:CHECKERBOARD_DIMS[1]].T.reshape(-1, 2)
                    objp = objp * SQUARE_SIZE

                    success, rvec, tvec = cv2.solvePnP(objp, corners, np.eye(3), None) # type: ignore
                    
                    if success:
                        # Store Robot Pose (Convert RotVec -> Matrix)
                        r_robot = R.from_rotvec(tcp_pose[3:6]).as_matrix()
                        t_robot = np.array(tcp_pose[0:3]).reshape(3, 1)
                        R_gripper2base.append(r_robot)
                        t_gripper2base.append(t_robot)
                        
                        # Store Camera Pose (Convert RotVec -> Matrix)
                        r_cam, _ = cv2.Rodrigues(rvec)
                        R_target2cam.append(r_cam)
                        t_target2cam.append(tvec)
                        
                        sample_count += 1
                        print(f"✅ Sample {sample_count} Saved! (Robot Z: {tcp_pose[2]:.3f}m)")
                        
                        # Visual Feedback (Flash Green)
                        cv2.drawChessboardCorners(display_frame, CHECKERBOARD_DIMS, corners, found)
                        cv2.imshow("Calibration View", display_frame)
                        cv2.waitKey(300)
                else:
                    print("⚠️ Checkerboard not found! Ensure all corners are visible and board is flat.")

            # --- QUIT COMMAND ---
            elif key == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\nAborted by user.")

    # --- CALCULATION ---
    if sample_count < 5:
        print(f"❌ Not enough samples ({sample_count}/5). Calibration aborted.")
    else:
        print("\n" + "-"*30)
        print("Computing Hand-Eye Calibration (Tsai Method)...")
        
        try:
            R_cam2gripper, t_cam2gripper = cv2.calibrateHandEye(
                R_gripper2base, t_gripper2base,
                R_target2cam, t_target2cam,
                method=cv2.CALIB_HAND_EYE_TSAI
            )

            print("✅ CALIBRATION SUCCESSFUL!")
            print(f"Camera Offset (from Gripper):")
            print(f"  X: {t_cam2gripper[0][0]:.4f} m")
            print(f"  Y: {t_cam2gripper[1][0]:.4f} m")
            print(f"  Z: {t_cam2gripper[2][0]:.4f} m")

            # Save to JSON
            output_data = {
                "translation_x": float(t_cam2gripper[0][0]),
                "translation_y": float(t_cam2gripper[1][0]),
                "translation_z": float(t_cam2gripper[2][0]),
                "rotation_matrix": R_cam2gripper.tolist()
            }
            
            os.makedirs("config", exist_ok=True)
            with open(SAVE_FILE, 'w') as f:
                json.dump(output_data, f, indent=4)
            print(f"💾 Calibration saved to: {os.path.abspath(SAVE_FILE)}")

        except Exception as e:
            print(f"❌ Calculation Error: {e}")

    # Cleanup
    bot.disconnect()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
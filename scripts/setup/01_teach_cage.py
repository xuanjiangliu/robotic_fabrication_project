import sys
import os
import json
import time
import cv2
import numpy as np
from scipy.spatial.transform import Rotation as R

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from pkg.drivers.ur_rtde_wrapper import URRobot

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '../../config/printer_cage.json')
CAMERA_CONFIG = os.path.join(os.path.dirname(__file__), '../../config/camera_offset.json')
CAMERA_INDEX = 1

# Vision Settings
CHECKERBOARD_DIMS = (8, 7)
SQUARE_SIZE = 0.015  # 15mm

# Safety Buffer (Shrink cage by this amount)
SAFETY_BUFFER = 0.020 

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def load_camera_calibration(path):
    """Loads the Hand-Eye matrix (T_cam_gripper) from JSON."""
    if not os.path.exists(path):
        print(f"⚠️ Camera calibration {path} not found! Vision anchor will be skipped.")
        return None
    
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        
        t_cg = np.eye(4)
        t_cg[:3, :3] = np.array(data["rotation_matrix"])
        t_cg[0, 3] = data["translation_x"]
        t_cg[1, 3] = data["translation_y"]
        t_cg[2, 3] = data["translation_z"]
        return t_cg
    except Exception as e:
        print(f"❌ Error loading camera config: {e}")
        return None

def capture_vision_anchor(bot, t_cam_gripper):
    """
    Interactive loop to find the checkerboard and calculate its pose in Base Frame.
    Returns: 4x4 Matrix (T_base_board) or None
    """
    print("\n👉 STEP 1: VISION ANCHOR")
    print("   1. Place the Checkerboard on the Print Bed (Center is best).")
    print("   2. Jog robot so the camera sees the board clearly.")
    print("   3. Press 'c' to Capture, 's' to Skip.")
    
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)
    
    # Fix for backend issues
    try:
        fourcc = cv2.VideoWriter.fourcc(*'MJPG') # type: ignore
    except AttributeError:
        fourcc = cv2.VideoWriter_fourcc(*'MJPG') # type: ignore
    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    anchor_pose = None

    while True:
        ret, frame = cap.read()
        if not ret: 
            time.sleep(0.1); continue
            
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(gray, CHECKERBOARD_DIMS, None)
        
        display_frame = frame.copy()
        if found:
            cv2.drawChessboardCorners(display_frame, CHECKERBOARD_DIMS, corners, found)
            cv2.putText(display_frame, "BOARD DETECTED - Press 'c'", (30, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        else:
            cv2.putText(display_frame, "Looking for Board...", (30, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
        cv2.imshow("Vision Anchor", display_frame)
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('s'):
            print("   Skipped Vision Anchor.")
            break
            
        if key == ord('c') and found:
            # 1. Refine
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            
            # 2. Get Robot Pose (T_gripper_base)
            tcp_pose = bot.get_tcp_pose() # [x,y,z,rx,ry,rz]
            if not tcp_pose:
                print("❌ Robot Pose Read Failed. Retrying...")
                continue
                
            # 3. Solve PnP (T_board_cam)
            objp = np.zeros((CHECKERBOARD_DIMS[0] * CHECKERBOARD_DIMS[1], 3), np.float32)
            objp[:, :2] = np.mgrid[0:CHECKERBOARD_DIMS[0], 0:CHECKERBOARD_DIMS[1]].T.reshape(-1, 2)
            objp = objp * SQUARE_SIZE
            
            success, rvec, tvec = cv2.solvePnP(objp, corners, np.eye(3), None) #type: ignore
            
            if success:
                # Math: T_base_board = T_base_gripper * T_gripper_cam * T_cam_board
                # We have T_cam_gripper. Invert it? No, typically T_cam_gripper means "Cam in Gripper Frame".
                # My calibration script saves T_cam_gripper (Cam relative to Gripper).
                # So P_gripper = T_cam_gripper * P_cam.
                
                # T_board_cam (Board in Camera Frame)
                t_board_cam = np.eye(4)
                t_board_cam[:3, :3] = cv2.Rodrigues(rvec)[0]
                t_board_cam[:3, 3] = tvec.reshape(3)
                
                # T_base_gripper (Gripper in Base Frame)
                t_base_gripper = np.eye(4)
                t_base_gripper[:3, :3] = R.from_rotvec(tcp_pose[3:6]).as_matrix()
                t_base_gripper[:3, 3] = tcp_pose[0:3]
                
                # Full Chain
                t_base_board = t_base_gripper @ t_cam_gripper @ t_board_cam
                
                anchor_pose = t_base_board.tolist() # Save as list for JSON
                
                print(f"✅ Vision Anchor Captured at Base XYZ: {t_base_board[:3, 3]}")
                break

    cap.release()
    cv2.destroyAllWindows()
    return anchor_pose

def main():
    clear_screen()
    print("--- RoboFab Virtual Cage & Vision Anchor ---")
    
    bot = URRobot(ROBOT_IP)
    if not bot.connect(): return

    # Load Calibration
    t_cam_gripper = load_camera_calibration(CAMERA_CONFIG)

    # Data Storage
    cage_data = {}
    
    # --- 1. VISION ANCHOR ---
    if t_cam_gripper is not None:
        cage_data["vision_anchor_pose_matrix"] = capture_vision_anchor(bot, t_cam_gripper)
    else:
        print("⚠️ Skipping Vision Anchor (No Calibration).")

    # --- 2. PHYSICAL LIMITS ---
    print("\n" + "-"*40)
    print("👉 STEP 2: TEACH PHYSICAL CAGE LIMITS")
    print("   Touch the ACTUAL physical limits. Software will apply safety buffer.")
    
    try:
        # Z Limits
        print("\n[HEIGHT] Touch Print Bed -> Press ENTER")
        input()
        p = bot.get_tcp_pose(); z_min = p[2] if p else 0.0
        print(f"   Bed Z: {z_min:.4f}")

        print("\n[HEIGHT] Touch Ceiling/Max -> Press ENTER")
        input()
        p = bot.get_tcp_pose(); z_max = p[2] if p else 0.5
        print(f"   Ceiling Z: {z_max:.4f}")

        # X Limits
        print("\n[WIDTH] Touch LEFT Wall -> Press ENTER")
        input()
        p = bot.get_tcp_pose(); x1 = p[0] if p else 0.0

        print("\n[WIDTH] Touch RIGHT Wall -> Press ENTER")
        input()
        p = bot.get_tcp_pose(); x2 = p[0] if p else 0.0
        
        x_min, x_max = min(x1, x2), max(x1, x2)

        # Y Limits
        print("\n[DEPTH] Touch BACK Wall -> Press ENTER")
        input()
        p = bot.get_tcp_pose(); y1 = p[1] if p else 0.0

        print("\n[DEPTH] Touch FRONT Frame -> Press ENTER")
        input()
        p = bot.get_tcp_pose(); y2 = p[1] if p else 0.0
        
        y_min, y_max = min(y1, y2), max(y1, y2)

        # Entry Pose
        print("\n[ENTRY] Move to Safe Hover Spot -> Press ENTER")
        input()
        entry_pose = bot.get_tcp_pose()

        # --- COMPUTE & SAVE ---
        cage_data.update({
            "x_min": x_min + SAFETY_BUFFER,
            "x_max": x_max - SAFETY_BUFFER,
            "y_min": y_min + SAFETY_BUFFER,
            "y_max": y_max - SAFETY_BUFFER,
            "z_min": z_min + SAFETY_BUFFER,
            "z_max": z_max - SAFETY_BUFFER,
            "entry_pose": entry_pose
        })

        # Sanity Check
        print("\n" + "="*40)
        print(f"Safety Buffer: {SAFETY_BUFFER*1000}mm")
        print(f"Safe Bounds X: {cage_data['x_min']:.3f} to {cage_data['x_max']:.3f}")
        print(f"Safe Bounds Y: {cage_data['y_min']:.3f} to {cage_data['y_max']:.3f}")
        print(f"Safe Bounds Z: {cage_data['z_min']:.3f} to {cage_data['z_max']:.3f}")
        
        if "vision_anchor_pose_matrix" in cage_data and cage_data["vision_anchor_pose_matrix"]:
             print("✅ Vision Anchor: LINKED")
        else:
             print("⚠️ Vision Anchor: NOT SET")

        if input("\n💾 Save to config/printer_cage.json? (y/n): ").lower() == 'y':
            os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
            with open(OUTPUT_FILE, 'w') as f:
                json.dump(cage_data, f, indent=4)
            print("✅ Configuration Saved.")

    except Exception as e:
        print(f"❌ Error during teaching: {e}")
    
    bot.disconnect()

if __name__ == "__main__":
    main()
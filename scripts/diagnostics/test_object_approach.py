import sys
import os
import time
import socket
import cv2
import numpy as np
from scipy.spatial.transform import Rotation as R

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from pkg.drivers.ur_rtde_wrapper import URRobot
from pkg.vision.eye_in_hand import EyeInHand

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
PORT_CMD = 30002            # Port for sending commands
CAMERA_INDEX = 1            # Orbbec RGB

# Motion Settings
ACCEL = 0.3                 
SPEED_FAST = 0.1            
SPEED_SLOW = 0.05           

# Heights (Relative logic)
TILT_Z_OFFSET = -0.05       # Drop 5cm from Start Height
TILT_ANGLE_DEG = 45         # Pitch down 45 degrees

# Vision Settings
THRESHOLD_VAL = 180         # White > 180

def init_camera_simple():
    """
    Exact copy of the working init from test_yolo_follow.py
    No fancy resets, just connect and force MJPG.
    """
    print(f"[Vision] Connecting to Camera {CAMERA_INDEX}...")
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)
    
    if cap.isOpened():
        # Force MJPG
        try:
            fourcc = cv2.VideoWriter.fourcc(*'MJPG') # type: ignore
        except AttributeError:
            fourcc = cv2.VideoWriter_fourcc(*'MJPG') # type: ignore
            
        cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        return cap
    return None

def detect_white_object(frame):
    """Returns (u, v, angle) of the largest white blob."""
    # Safety Check
    if frame is None or frame.size == 0:
        return None, frame

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, THRESHOLD_VAL, 255, cv2.THRESH_BINARY)
    
    # Clean noise
    mask = cv2.erode(mask, None, iterations=2) # type: ignore
    mask = cv2.dilate(mask, None, iterations=2) # type: ignore
    
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    output_frame = frame.copy()
    
    if contours:
        c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(c) > 500: # Min area filter
            rect = cv2.minAreaRect(c)
            (center_u, center_v), _, angle = rect
            
            # Draw UI
            box = cv2.boxPoints(rect)
            box = np.int0(box) # type: ignore
            cv2.drawContours(output_frame, [box], 0, (0, 255, 0), 2) # type: ignore
            cv2.circle(output_frame, (int(center_u), int(center_v)), 5, (0, 0, 255), -1) # type: ignore
            cv2.putText(output_frame, f"TGT: {int(center_u)},{int(center_v)}", 
                       (int(center_u)+10, int(center_v)), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2) # type: ignore
            
            return (center_u, center_v, angle), output_frame
            
    return None, output_frame

def fmt_pose(x, y, z, rx, ry, rz):
    return f"p[{x:.4f}, {y:.4f}, {z:.4f}, {rx:.4f}, {ry:.4f}, {rz:.4f}]"

def main():
    print("--- RoboFab Manual-Entry Object Approach ---")
    
    # 1. Setup Camera (Simple Method)
    cap = init_camera_simple()
    if cap is None or not cap.isOpened():
        print("❌ Camera Failed.")
        return
    
    eye = EyeInHand()

    # 2. Setup Robot Reader
    bot_reader = URRobot(ROBOT_IP)
    if not bot_reader.connect(): return

    # 3. Setup Robot Commander
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try: sock.connect((ROBOT_IP, PORT_CMD))
    except: print("❌ Socket Failed"); return

    try:
        # --- PHASE 1: MONITOR & CAPTURE ---
        print("\n" + "="*50)
        print("👉 PHASE 1: LIVE MONITOR")
        print("1. Manually jog robot so Camera is LEVEL and sees the object.")
        print("2. This position will be the SAFE HOME.")
        print("3. Press 'SPACE' to Lock Target & Proceed.")
        print("   Press 'q' to Quit.")
        print("="*50)

        start_pose = None
        target_u, target_v = None, None
        
        while True:
            ret, frame = cap.read()
            
            # Skip empty frames (Don't crash)
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            # Detect
            det_result, vis_frame = detect_white_object(frame)
            
            # UI
            if det_result:
                target_u, target_v, _ = det_result
                cv2.putText(vis_frame, "LOCKED - READY", (30, 30), # type: ignore
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            else:
                cv2.putText(vis_frame, "SEARCHING...", (30, 30), # type: ignore
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            cv2.imshow("Live Feed", vis_frame) # type: ignore
            
            key = cv2.waitKey(10) & 0xFF
            if key == ord(' '):
                if target_u is not None:
                    # CAPTURE POSE NOW
                    start_pose = bot_reader.get_tcp_pose()
                    if start_pose:
                        print(f"✅ Target Locked: ({target_u}, {target_v})")
                        print(f"✅ Safe Home Captured: {start_pose[:3]}")
                        break
                    else:
                        print("❌ Failed to read robot pose!")
                else:
                    print("❌ No object visible!")
            elif key == ord('q'):
                return

        # --- PHASE 2: CALCULATE ---
        print("\n👉 PHASE 2: CALCULATION")
        # Calc World Target
        tx, ty = eye.pixel_to_robot(target_u, target_v, start_pose)
        print(f"   🎯 World Target: X={tx:.4f}, Y={ty:.4f}")
        
        # Calc Tilt Rotation (Pitch Down relative to current)
        current_rot_vec = start_pose[3:6]
        r_curr = R.from_rotvec(current_rot_vec)
        
        # Apply 45 deg tilt around X-axis (Camera pitch)
        tilt_delta = R.from_euler('x', TILT_ANGLE_DEG, degrees=True)
        r_new = r_curr * tilt_delta 
        tilt_rot_vec = r_new.as_rotvec().tolist()
        
        safe_z = start_pose[2]
        tilt_z = safe_z + TILT_Z_OFFSET

        # --- PHASE 3: LINEAR APPROACH ---
        print("\n👉 PHASE 3: EXECUTION")
        script = "def approach_sequence():\n"
        
        # 1. Align X/Y (Maintain Height & Rotation)
        script += f"  movel({fmt_pose(tx, ty, safe_z, *current_rot_vec)}, a={ACCEL}, v={SPEED_FAST})\n"
        
        # 2. Descend (Maintain Rotation) -> Object disappears
        script += f"  movel({fmt_pose(tx, ty, tilt_z, *current_rot_vec)}, a={ACCEL}, v={SPEED_FAST})\n"
        
        # 3. Tilt (Twist Wrist) -> Object reappears
        script += f"  movel({fmt_pose(tx, ty, tilt_z, *tilt_rot_vec)}, a={ACCEL}, v={SPEED_SLOW})\n"
        
        script += "end\n"
        script += "approach_sequence()\n"
        
        print("🚀 Sending Command...")
        sock.sendall(script.encode())
        
        # Wait + Buffer
        time.sleep(6.0)

        # --- PHASE 4: VERIFY ---
        print("\n👉 PHASE 4: VERIFY")
        # Flush Buffer
        for _ in range(5): cap.read()

        ret, frame = cap.read()
        if ret and frame is not None:
            res, final_frame = detect_white_object(frame)
            cv2.imshow("Live Feed", final_frame) # type: ignore
            cv2.waitKey(3000)
            
            if res:
                print("✅ SUCCESS: Object re-acquired after tilt!")
            else:
                print("⚠️ FAIL: Object not seen. Adjust TILT_ANGLE_DEG or TILT_Z_OFFSET.")
        else:
            print("❌ Camera read failed during verification.")
        
    except KeyboardInterrupt:
        print("\nAborted.")
        sock.sendall(b"stopj(2.0)\n")
    
    finally:
        sock.close()
        bot_reader.disconnect()
        if cap: cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
import sys
import os
import time
import cv2
import socket
import numpy as np
from ultralytics import YOLO

# --- SAFETY CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
CAMERA_INDEX = 1        # Orbbec RGB
SPEED_GAIN = 0.5        # Sensitivity
MAX_SPEED = 0.1         # Speed Limit (m/s)
DEADZONE = 0.1          # Ignore small jitters
ACCELERATION = 0.5      # Snappiness

# --- DIRECTION MAPPING (UPDATED) ---
# X_AXIS_GAIN controls Robot Y (Lateral Side-to-Side)
# Changed from -1.0 to 1.0 to fix the "Reverse" issue
X_AXIS_GAIN = 1.0  

# Y_AXIS_GAIN controls Robot X (Forward/Backward Reach)
# Set to 0.0 to DISABLE reaching
Y_AXIS_GAIN = 0.0 

def init_camera_robust():
    """Force MJPG to avoid Windows crash."""
    print(f"Connecting to Camera {CAMERA_INDEX}...")
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        return cap
    return None

def send_speed_command(s, vx, vy):
    # speedl([x, y, z, rx, ry, rz], a, t)
    cmd = f"speedl([{vx:.3f},{vy:.3f},0,0,0,0], a={ACCELERATION}, t=0.1)\n"
    try:
        s.sendall(cmd.encode('utf-8'))
    except:
        pass

def main():
    print("--- RoboFab Lateral Follower ---")
    print("Loading YOLO...")
    model = YOLO('yolov8n-pose.pt') 
    
    # Connect Robot
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect((ROBOT_IP, 30002))
        print("✅ Robot Connected.")
    except Exception as e:
        print(f"❌ Robot Connection Failed: {e}")
        return

    # Connect Camera
    cap = init_camera_robust()
    if cap is None:
        print("❌ Camera Failed.")
        return

    # --- SAFETY BLOCK ---
    print("\n" + "!"*40)
    print("⚠️  SAFETY CHECKPOINT")
    print("   Mode: LATERAL ONLY (No Reach)")
    print("   Hand Right -> Robot Right")
    print("!"*40)
    input("👉 PRESS ENTER TO ENABLE MOTION... ")
    print("🚀 MOTION ACTIVE! Raise Right Hand.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret: break

            results = model(frame, verbose=False, conf=0.5)
            vx, vy = 0.0, 0.0
            status = "IDLE"
            color = (0, 0, 255)

            if results[0].keypoints is not None:
                kpts = results[0].keypoints.data
                if len(kpts) > 0:
                    # Get Right Wrist (Keypoint 10)
                    wrist = kpts[0][10]
                    wx, wy, conf = float(wrist[0]), float(wrist[1]), float(wrist[2])

                    if conf > 0.5:
                        cv2.circle(frame, (int(wx), int(wy)), 15, (0, 255, 0), 2)
                        
                        # Calculate Error (-0.5 to 0.5)
                        h, w, _ = frame.shape
                        err_x = (wx / w) - 0.5
                        err_y = (wy / h) - 0.5
                        
                        if abs(err_x) > DEADZONE:
                            # Map Image X (Side) to Robot Lateral Velocity
                            vy += err_x * X_AXIS_GAIN * SPEED_GAIN
                            
                            # Map Image Y (Up/Down) to Robot Reach
                            # (Disabled because Y_AXIS_GAIN is 0.0)
                            vx += err_y * Y_AXIS_GAIN * SPEED_GAIN
                            
                            status = "TRACKING"
                            color = (0, 255, 0)

            # Clamp Speed
            vx = max(min(vx, MAX_SPEED), -MAX_SPEED)
            vy = max(min(vy, MAX_SPEED), -MAX_SPEED)

            if status == "TRACKING":
                send_speed_command(s, vx, vy)
            else:
                send_speed_command(s, 0, 0) 

            # UI
            cv2.putText(frame, f"VEL: {vx:.2f}, {vy:.2f}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.imshow("YOLO Safe Follow", frame)
            
            if cv2.waitKey(1) == ord('q'): break

    except KeyboardInterrupt:
        pass
    finally:
        print("Stopping Robot...")
        s.sendall(b"stopj(2.0)\n")
        s.close()
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
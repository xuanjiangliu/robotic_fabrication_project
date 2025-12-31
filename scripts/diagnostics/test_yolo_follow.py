import sys
import os
import time
import cv2
import socket
import numpy as np
from ultralytics import YOLO # type: ignore

# --- SAFETY CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
CAMERA_INDEX = 1        # Orbbec RGB

# Motion Settings
SPEED_GAIN = 0.8        # Base Rotation Sensitivity
LIFT_GAIN = 0.3         # Vertical Lift Sensitivity (Kept SLOW as requested)
MAX_SPEED_RAD = 0.5     # Speed Limit (~30 deg/s)
DEADZONE = 0.1          # Ignore small jitters
ACCELERATION = 0.5      # Smooth acceleration

# --- DIRECTION MAPPING ---
# Base Rotation: -1.0 (Reversed per your preference)
ROTATION_DIR = -1.0  

# Lift Direction: 1.0 
# (If robot moves DOWN when hand goes UP, change this to -1.0)
LIFT_DIR = 1.0

def init_camera_robust():
    """Force MJPG to avoid Windows crash."""
    print(f"Connecting to Camera {CAMERA_INDEX}...")
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG')) # type: ignore
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        return cap
    return None

def send_joint_speed(s, base_vel, shoulder_vel):
    """
    Uses speedj to control Base (0) and Shoulder (1).
    """
    # speedj([Base, Shoulder, Elbow, W1, W2, W3], a, t)
    cmd = f"speedj([{base_vel:.3f},{shoulder_vel:.3f},0,0,0,0], a={ACCELERATION}, t=0.1)\n"
    try:
        s.sendall(cmd.encode('utf-8'))
    except:
        pass

def main():
    print("--- RoboFab Turret + Lift (Joint Control) ---")
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
    print("   1. ROTATION: Left/Right Hand -> Base Pan")
    print("   2. LIFT: Up/Down Hand -> Shoulder Rotate")
    print("   Note: Robot arm will arc slightly when lifting.")
    print("!"*40)
    input("👉 PRESS ENTER TO ENABLE MOTION... ")
    print("🚀 MOTION ACTIVE! Raise Right Hand.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret: break

            results = model(frame, verbose=False, conf=0.5)
            base_vel = 0.0
            shoulder_vel = 0.0
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
                        
                        # --- 1. Horizontal Control (Base) ---
                        h, w, _ = frame.shape
                        err_x = (wx / w) - 0.5
                        
                        # --- 2. Vertical Control (Shoulder) ---
                        # Pixel 0 is Top, so (wy/h) is small when hand is up.
                        # We want Up Hand -> Up Robot.
                        # err_y will be negative when hand is high.
                        err_y = (wy / h) - 0.5
                        
                        if abs(err_x) > DEADZONE or abs(err_y) > DEADZONE:
                            # Map Errors to Velocities
                            base_vel += err_x * ROTATION_DIR * SPEED_GAIN
                            
                            # For Lift: We usually flip Y because Image Y is inverted (Top=0)
                            # -err_y means "Negative error" (Hand High) -> Positive Velocity (Lift Up?)
                            # You may need to flip LIFT_DIR if it moves wrong.
                            shoulder_vel += -err_y * LIFT_DIR * LIFT_GAIN
                            
                            status = "TRACKING"
                            color = (0, 255, 0)

            # Clamp Speeds
            base_vel = max(min(base_vel, MAX_SPEED_RAD), -MAX_SPEED_RAD)
            shoulder_vel = max(min(shoulder_vel, MAX_SPEED_RAD), -MAX_SPEED_RAD)

            if status == "TRACKING":
                send_joint_speed(s, base_vel, shoulder_vel)
            else:
                send_joint_speed(s, 0.0, 0.0) 

            # UI
            cv2.putText(frame, f"B:{base_vel:.2f} S:{shoulder_vel:.2f}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.imshow("RoboFab Turret + Lift", frame)
            
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
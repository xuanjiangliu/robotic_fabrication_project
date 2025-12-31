import sys
import os
import time
import socket
import cv2
import numpy as np

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from pkg.drivers.ur_rtde_wrapper import URRobot

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
PORT_CMD = 30002
CAMERA_INDEX = 1

# Vision Settings
IMG_W, IMG_H = 1280, 720
CENTER_X, CENTER_Y = IMG_W // 2, IMG_H // 2
WHITE_THRESHOLD = 170       

# Control Tuning
CURRENT_GAIN = 0.0005       
MAX_SPEED_LATERAL = 0.08    
MAX_SPEED_Z = 0.05          

# --- DIRECTION CORRECTION ---
# Toggle these if the robot moves the wrong way!
INVERT_X_AXIS = True   # Toggles Reach (Forward/Back)
INVERT_Y_AXIS = False  # Toggles Slide (Left/Right)

# Fluid Logic Settings
DESCENT_RADIUS = 300        # Start descending if object is within this pixel radius
TRACKING_RADIUS = 250
LOST_TIMEOUT = 10

def init_camera_robust():
    print(f"[Vision] Connecting to Camera {CAMERA_INDEX}...")
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)
    if cap.isOpened():
        try:
            fourcc = cv2.VideoWriter_fourcc(*'MJPG') # type: ignore
        except:
            fourcc = cv2.VideoWriter_fourcc(*'MJPG') # type: ignore
        cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, IMG_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, IMG_H)
        for _ in range(10): cap.read()
        return cap
    return None

def detect_with_tracking(frame, last_pos, current_z):
    h, w = frame.shape[:2]
    mask_roi = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(mask_roi, (300, 150), (1100, 720), 255, -1) # type: ignore

    scale = max(0.1, 0.3 / max(current_z, 0.01))
    min_area = 500 * scale
    max_area = 30000 * scale * scale

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, WHITE_THRESHOLD, 255, cv2.THRESH_BINARY)
    binary = cv2.bitwise_and(binary, binary, mask=mask_roi)
    binary = cv2.erode(binary, None, iterations=2) # type: ignore
    binary = cv2.dilate(binary, None, iterations=2) # type: ignore
    
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    vis = frame.copy()
    cv2.rectangle(vis, (300, 150), (1100, 720), (0, 255, 255), 1) # type: ignore

    best_pt = None
    min_dist = float('inf')

    if contours:
        for c in contours:
            area = cv2.contourArea(c)
            if area < min_area or area > max_area: continue
            
            x,y,bw,bh = cv2.boundingRect(c)
            ar = float(bw)/bh if bh>0 else 0
            if ar > 3.0 or ar < 0.33: continue

            M = cv2.moments(c)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                if last_pos:
                    dist = np.sqrt((cx - last_pos[0])**2 + (cy - last_pos[1])**2)
                    if dist > TRACKING_RADIUS: continue
                else:
                    dist = np.sqrt((cx - CENTER_X)**2 + (cy - CENTER_Y)**2)

                if dist < min_dist:
                    min_dist = dist
                    best_pt = (cx, cy)
                    best_c = c
    
    if best_pt:
        cv2.drawContours(vis, [best_c], -1, (0, 255, 0), 2) # type: ignore
        return best_pt[0], best_pt[1], vis
    
    return None, None, vis

def main():
    global CURRENT_GAIN
    
    cap = init_camera_robust()
    if not cap: return
    
    bot_reader = URRobot(ROBOT_IP)
    if not bot_reader.connect(): return
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ROBOT_IP, PORT_CMD))

    print("\n✅ FLUID SERVO READY.")
    print("   [SPACE] Toggle Active Mode")
    print("   [UP/DWN] Adjust XY Gain")
    print("   [q] Quit")
    print(f"   ℹ️ Direction Flip: X={INVERT_X_AXIS}, Y={INVERT_Y_AXIS}")

    active = False
    last_pos = None
    lost_frames = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret: break

            tcp = bot_reader.get_tcp_pose()
            curr_z = tcp[2] if tcp else 0.3
            
            u, v, vis = detect_with_tracking(frame, last_pos, curr_z)
            
            # Draw Safe Descent Zone
            cv2.circle(vis, (CENTER_X, CENTER_Y), DESCENT_RADIUS, (0, 255, 255), 1) # type: ignore

            vx, vy, vz = 0.0, 0.0, 0.0
            status = "IDLE"

            if u is not None:
                last_pos = (u, v)
                lost_frames = 0
                
                err_u = u - CENTER_X # type: ignore
                err_v = v - CENTER_Y # type: ignore
                dist_error = np.sqrt(err_u**2 + err_v**2)
                
                # Visual Feedback
                cv2.arrowedLine(vis, (CENTER_X, CENTER_Y), (u, v), (0, 0, 255), 2) # type: ignore

                if active:
                    # Apply Inversion Flags
                    dir_x = -1.0 if INVERT_X_AXIS else 1.0
                    dir_y = -1.0 if INVERT_Y_AXIS else 1.0

                    # 1. LATERAL CONTROL
                    # U -> Robot Y (Side), V -> Robot X (Reach)
                    vy = err_u * CURRENT_GAIN * dir_y
                    vx = err_v * CURRENT_GAIN * dir_x
                    
                    vx = max(min(vx, MAX_SPEED_LATERAL), -MAX_SPEED_LATERAL)
                    vy = max(min(vy, MAX_SPEED_LATERAL), -MAX_SPEED_LATERAL)

                    # 2. FLUID DESCENT
                    if dist_error < DESCENT_RADIUS:
                        if curr_z > 0.05:
                            # Scale speed: Fast when centered, slow at edge
                            factor = max(0.2, (DESCENT_RADIUS - dist_error) / DESCENT_RADIUS)
                            vz = -MAX_SPEED_Z * factor
                            status = f"FLUID APPR ({int(factor*100)}%)"
                        else:
                            vz = 0.0
                            status = "GRAB READY (Z Limit)"
                    else:
                        vz = 0.0
                        status = "ALIGNING (Too Far)"

                    cmd = f"speedl([{vx:.4f},{vy:.4f},{vz:.4f},0,0,0], a=0.3, t=0.1)\n"
                    sock.sendall(cmd.encode())

            elif active:
                lost_frames += 1
                status = f"LOST {lost_frames}"
                if lost_frames > LOST_TIMEOUT:
                    last_pos = None
                    sock.sendall(b"speedl([0,0,0,0,0,0], a=0.5, t=0.1)\n")

            # HUD
            color = (0, 255, 0) if active else (0, 0, 255)
            cv2.putText(vis, f"MODE: {status}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2) # type: ignore
            cv2.putText(vis, f"XY GAIN: {CURRENT_GAIN:.5f}", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2) # type: ignore
            cv2.putText(vis, f"Z: {curr_z:.3f}m", (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2) # type: ignore

            cv2.imshow("Fluid Servo", vis) # type: ignore
            
            key = cv2.waitKeyEx(1)
            if key == ord(' '): active = not active
            elif key == ord('q'): break
            elif key == 2490368: CURRENT_GAIN += 0.0001   # UP
            elif key == 2621440: CURRENT_GAIN = max(0.0001, CURRENT_GAIN - 0.0001) # DOWN

    finally:
        print("Stopping...")
        sock.sendall(b"stopj(1.0)\n")
        sock.close()
        bot_reader.disconnect()
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
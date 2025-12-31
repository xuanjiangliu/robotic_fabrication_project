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

# --- DIRECTION FLAGS (Matched to your working Planar Script) ---
INVERT_SIDE = True      # True = Multiply by -1.0
INVERT_REACH = True     # True = Multiply by -1.0

# Vision Goals
TARGET_AREA_PERCENT = 0.20
IMG_W, IMG_H = 1280, 720
CENTER_X = IMG_W // 2

# Control Tuning
GAIN_SIDE = 0.0005
GAIN_REACH = 0.5
MAX_SPEED = 0.05

# --- ROBUSTNESS SETTINGS ---
TRACKING_RADIUS = 100   # Strict: Only look 100px around last object
MAX_JUMP = 50           # Strict: Ignore blobs that jump > 50px/frame
LOST_TIMEOUT = 20       # Frames to wait before triggering Return

# Filters
WHITE_THRESHOLD = 160
MIN_AREA_PIXELS = 100

def init_camera_robust():
    print(f"[Vision] Connecting to Camera {CAMERA_INDEX}...")
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)
    if cap.isOpened():
        try:
            fourcc = cv2.VideoWriter.fourcc(*'MJPG') # type: ignore
        except:
            fourcc = cv2.VideoWriter_fourcc(*'MJPG') # type: ignore
        cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, IMG_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, IMG_H)
        for _ in range(10): cap.read()
        return cap
    return None

def fmt_pose(p):
    return f"p[{p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f}, {p[3]:.4f}, {p[4]:.4f}, {p[5]:.4f}]"

def detect_object_strict(frame, last_pos):
    h, w = frame.shape[:2]
    
    # ROI (Ignore Window Glare)
    mask_roi = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(mask_roi, (300, 150), (1100, 720), 255, -1)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, WHITE_THRESHOLD, 255, cv2.THRESH_BINARY)
    binary = cv2.bitwise_and(binary, binary, mask=mask_roi)
    binary = cv2.erode(binary, None, iterations=2) # type: ignore
    
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    vis = frame.copy()
    cv2.rectangle(vis, (300, 150), (1100, 720), (0, 100, 100), 1)

    best_c = None
    max_score = -1
    found_center = None
    found_area = 0

    if last_pos:
        cv2.circle(vis, last_pos, TRACKING_RADIUS, (0, 255, 255), 2)

    if contours:
        for c in contours:
            area = cv2.contourArea(c)
            if area < MIN_AREA_PIXELS: continue
            
            x,y,bw,bh = cv2.boundingRect(c)
            ar = float(bw)/bh if bh>0 else 0
            if ar > 3.0 or ar < 0.33: continue

            M = cv2.moments(c)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                if last_pos:
                    # STRICT LOCKING
                    dist = np.sqrt((cx - last_pos[0])**2 + (cy - last_pos[1])**2)
                    
                    if dist > TRACKING_RADIUS: 
                        cv2.drawContours(vis, [c], -1, (0, 0, 255), 1) # Rejected (Too far)
                        continue
                    if dist > MAX_JUMP:
                        cv2.drawContours(vis, [c], -1, (0, 0, 255), 1) # Rejected (Jumped)
                        continue
                    score = area
                else:
                    score = area

                if score > max_score:
                    max_score = score
                    best_c = c
                    found_center = (cx, cy)
                    found_area = area

    if best_c is not None:
        cv2.drawContours(vis, [best_c], -1, (0, 255, 0), 2)
        return found_center, found_area, vis
    
    return None, 0, vis

def main():
    cap = init_camera_robust()
    if not cap: return
    
    bot_reader = URRobot(ROBOT_IP)
    if not bot_reader.connect(): return
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ROBOT_IP, PORT_CMD))

    print("\n✅ ROBUST SERVO READY (Matched Logic).")
    print("   [SPACE] Start (Captures HOME)")
    print("   [q] Quit")
    
    active = False
    start_pose = None
    last_pos = None
    lost_frames = 0
    target_pixels = (IMG_W * IMG_H) * TARGET_AREA_PERCENT

    try:
        while True:
            ret, frame = cap.read()
            if not ret: break

            center, area, vis = detect_object_strict(frame, last_pos)
            
            vx_base, vy_base = 0.0, 0.0
            status = "IDLE"

            # --- 1. OBJECT FOUND ---
            if center is not None:
                last_pos = center
                lost_frames = 0
                u, v = center
                cv2.circle(vis, center, 5, (0, 0, 255), -1)
                
                if active:
                    err_x_px = u - CENTER_X 
                    area_ratio = area / target_pixels
                    err_reach = (1.0 - area_ratio)

                    # --- CORRECTED LOGIC (Matches your Planar Script) ---
                    dir_side = -1.0 if INVERT_SIDE else 1.0
                    dir_reach = 1.0 if INVERT_REACH else -1.0

                    vy_base = err_x_px * GAIN_SIDE * dir_side
                    vx_base = err_reach * GAIN_REACH * dir_reach

                    # Deadbands
                    if abs(err_x_px) < 20: vy_base = 0.0
                    if abs(err_reach) < 0.05: vx_base = 0.0
                    
                    status = "REACHING" if abs(err_x_px) < 100 else "ALIGNING"
                    
                    vx_base = max(min(vx_base, MAX_SPEED), -MAX_SPEED)
                    vy_base = max(min(vy_base, MAX_SPEED), -MAX_SPEED)

                    cmd = f"speedl([{vx_base:.4f},{vy_base:.4f},0.0,0,0,0], a=0.3, t=0.1)\n"
                    sock.sendall(cmd.encode())
                    
                    # Debug Arrow
                    cv2.arrowedLine(vis, (CENTER_X, IMG_H//2), 
                                   (int(CENTER_X + vy_base*5000), int(IMG_H//2 - vx_base*5000)), 
                                   (255,0,0), 3)

            # --- 2. OBJECT LOST ---
            elif active:
                lost_frames += 1
                
                if lost_frames > LOST_TIMEOUT:
                    # TRIGGER RETURN
                    if start_pose:
                        status = "RETURNING HOME"
                        cv2.putText(vis, "RETURNING...", (CENTER_X-150, CENTER_Y), # type: ignore
                                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
                        cv2.imshow("Robust Servo", vis)
                        cv2.waitKey(1)
                        
                        # Stop -> MoveL -> Reset
                        sock.sendall(b"stopj(2.0)\n")
                        time.sleep(0.5)
                        
                        print("🔙 Executing Blind Return...")
                        cmd = f"movel({fmt_pose(start_pose)}, a=0.5, v=0.15)\n"
                        sock.sendall(cmd.encode())
                        
                        time.sleep(4.0) # Wait for move to finish
                        
                        last_pos = None # Reset Tracking
                        lost_frames = 0
                        print("👀 Returned. Scanning...")
                        for _ in range(5): cap.read() # Clear buffer
                    else:
                        status = "LOST (No Home Set)"
                else:
                    status = f"MISSING ({lost_frames})"
                    sock.sendall(b"speedl([0,0,0,0,0,0], a=0.5, t=0.1)\n")

            cv2.putText(vis, f"MODE: {status}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0) if active else (0,0,255), 2)
            cv2.imshow("Robust Servo", vis)

            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '): 
                active = not active
                if active:
                    start_pose = bot_reader.get_tcp_pose()
                    last_pos = None
                    lost_frames = 0
                    print(f"🏠 Home Captured: {start_pose[:3]}") # type: ignore
            elif key == ord('q'): break

    except KeyboardInterrupt:
        pass
    finally:
        sock.sendall(b"stopj(1.0)\n")
        sock.close()
        bot_reader.disconnect()
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
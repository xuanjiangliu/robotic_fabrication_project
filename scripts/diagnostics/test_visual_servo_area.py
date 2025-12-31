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

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
PORT_CMD = 30002
CAMERA_INDEX = 1

# Vision Goals
TARGET_AREA_PERCENT = 0.15  # Stop when object fills 15% of screen
IMG_W, IMG_H = 1280, 720
CENTER_X, CENTER_Y = IMG_W // 2, IMG_H // 2

# --- SPEED SETTINGS (LOWERED FOR SAFETY) ---
GAIN_XY = 0.5       # Was 1.5 -> Responsive but smooth
GAIN_Z = 0.5        # Was 1.0 -> Slow approach
MAX_SPEED_L = 0.04  # Max Lateral Speed: 4cm/s (Very safe)
MAX_SPEED_Z = 0.03  # Max Approach Speed: 3cm/s

# Tracking Settings
TRACKING_RADIUS = 200       # Only look for object within 200px of last position
LOST_TIMEOUT = 10           # Frames to wait before resetting search

# Filters
WHITE_THRESHOLD = 160
MIN_AREA_PIXELS = 100
MAX_ASPECT = 3.0    # Reject long lines

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

def get_base_velocity(v_cam_x, v_cam_y, v_cam_z, robot_tcp_pose):
    """
    Transforms velocity from Camera Frame -> Robot Base Frame.
    """
    # 1. Get Robot Rotation Matrix (Base -> Tool)
    r_vec = robot_tcp_pose[3:6]
    r_base_tool = R.from_rotvec(r_vec).as_matrix()
    
    # 2. Define Camera -> Tool Rotation 
    # Cam Right (X) -> Robot Tool Y (neg)
    # Cam Down (Y)  -> Robot Tool X (neg)
    # Cam Forward (Z)-> Robot Tool Z (pos)
    v_tool = np.array([-v_cam_y, -v_cam_x, v_cam_z]) 

    # 3. Rotate to Base Frame
    v_base = r_base_tool @ v_tool
    return v_base

def detect_object_tracked(frame, last_pos):
    """
    Finds object. If last_pos exists, prioritizes objects near it.
    """
    h, w = frame.shape[:2]
    
    # ROI (Ignore Window Glare)
    mask_roi = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(mask_roi, (300, 150), (1100, 720), 255, -1)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, WHITE_THRESHOLD, 255, cv2.THRESH_BINARY)
    binary = cv2.bitwise_and(binary, binary, mask=mask_roi)
    binary = cv2.erode(binary, None, iterations=2) # type: ignore
    binary = cv2.dilate(binary, None, iterations=2) # type: ignore
    
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    vis = frame.copy()
    cv2.rectangle(vis, (300, 150), (1100, 720), (0, 100, 100), 1)
    
    # Draw Search Radius if tracking
    if last_pos:
        cv2.circle(vis, last_pos, TRACKING_RADIUS, (255, 0, 255), 1)

    best_c = None
    max_score = -1
    found_center = None
    found_area = 0

    if contours:
        for c in contours:
            area = cv2.contourArea(c)
            if area < MIN_AREA_PIXELS: continue
            
            x,y,bw,bh = cv2.boundingRect(c)
            ar = float(bw)/bh if bh>0 else 0
            if ar > MAX_ASPECT or ar < 1.0/MAX_ASPECT: continue

            M = cv2.moments(c)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                # SCORING LOGIC
                if last_pos:
                    # TRACKING MODE: Score = Area, but filter by Distance
                    dist = np.sqrt((cx - last_pos[0])**2 + (cy - last_pos[1])**2)
                    if dist > TRACKING_RADIUS:
                        continue # Ignore this blob, it's too far (likely distraction)
                    score = area # Pick largest valid blob in radius
                else:
                    # SEARCH MODE: Score = Area (Just find the big object)
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

    print("\n✅ AREA SERVO (TRACKING + SAFE SPEED) READY.")
    print("   [SPACE] Toggle Active Mode")
    print("   [q] Quit")
    
    active = False
    last_pos = None # Stores (u, v) of locked object
    lost_frames = 0
    
    # Target Pixels
    target_pixels = (IMG_W * IMG_H) * TARGET_AREA_PERCENT

    try:
        while True:
            ret, frame = cap.read()
            if not ret: break

            # Use Tracking Function
            center, area, vis = detect_object_tracked(frame, last_pos)
            tcp = bot_reader.get_tcp_pose()
            
            # HUD Overlay
            cv2.line(vis, (CENTER_X-20, CENTER_Y), (CENTER_X+20, CENTER_Y), (0,255,255), 1)
            cv2.line(vis, (CENTER_X, CENTER_Y-20), (CENTER_X, CENTER_Y+20), (0,255,255), 1)
            
            vx_cam, vy_cam, vz_cam = 0.0, 0.0, 0.0
            status = "IDLE"

            if center is not None and tcp is not None:
                # Update Tracker
                last_pos = center
                lost_frames = 0
                
                u, v = center
                cv2.circle(vis, center, 5, (0, 0, 255), -1)
                
                # 1. LATERAL ERROR
                err_x = (u - CENTER_X) / IMG_W
                err_y = (v - CENTER_Y) / IMG_H
                
                # 2. DEPTH ERROR
                area_ratio = area / target_pixels
                err_z = (1.0 - area_ratio) 

                if active:
                    # Calculate Cam Velocities
                    vx_cam = err_x * GAIN_XY
                    vy_cam = err_y * GAIN_XY
                    
                    # Only Approach if somewhat aligned (prevent spiral dives)
                    if abs(err_x) < 0.2 and abs(err_y) < 0.2:
                        vz_cam = err_z * GAIN_Z
                        status = "APPROACHING"
                    else:
                        vz_cam = 0.0
                        status = "ALIGNING"

                    # Clamp Speeds (Safety Cap)
                    vx_cam = max(min(vx_cam, MAX_SPEED_L), -MAX_SPEED_L)
                    vy_cam = max(min(vy_cam, MAX_SPEED_L), -MAX_SPEED_L)
                    vz_cam = max(min(vz_cam, MAX_SPEED_Z), -MAX_SPEED_Z)
                    
                    # Stop if Z-limit reached
                    if tcp[2] < 0.05: 
                        vz_cam = min(0, vz_cam) # Only allow pulling up
                        status = "GRAB LIMIT"

                    # 3. TRANSFORM (The magic part)
                    v_base = get_base_velocity(vx_cam, vy_cam, vz_cam, tcp)
                    
                    cmd = f"speedl([{v_base[0]:.4f},{v_base[1]:.4f},{v_base[2]:.4f},0,0,0], a=0.3, t=0.1)\n"
                    sock.sendall(cmd.encode())
                
                # HUD Bar
                bar_h = int(200 * area_ratio)
                color_bar = (0,255,0) if area_ratio > 0.9 else (0,255,255)
                cv2.rectangle(vis, (20, 400), (50, 400-bar_h), color_bar, -1)
                cv2.rectangle(vis, (20, 200), (50, 400), (255,255,255), 2)
                cv2.putText(vis, f"Area: {int(area_ratio*100)}%", (10, 420), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_bar, 2)

            elif active:
                # Lost Target Logic
                lost_frames += 1
                status = f"LOST ({lost_frames})"
                if lost_frames > LOST_TIMEOUT:
                    last_pos = None # Reset tracking to find new objects
                    status = "SEARCHING"
                
                sock.sendall(b"speedl([0,0,0,0,0,0], a=0.5, t=0.1)\n")

            cv2.putText(vis, f"MODE: {status}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0) if active else (0,0,255), 2)
            cv2.imshow("Area Servo", vis)

            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '): 
                active = not active
                if active: last_pos = None # Reset tracker on start
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
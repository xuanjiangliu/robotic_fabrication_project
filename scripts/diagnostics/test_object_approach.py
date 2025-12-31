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
PORT_CMD = 30002            
CAMERA_INDEX = 1            

# Heights (Meters)
SEARCH_Z = 0.35             
HOVER_Z = 0.15              
GRAB_Z = 0.05               
TILT_ANGLE_DEG = 45         

# Vision Tuning
WHITE_THRESHOLD = 160       # Lowered slightly to catch the Benchy better
MIN_AREA = 500              # Ignore small specks
MAX_AREA = 50000            # Ignore massive blobs (like walls)

def init_camera_robust():
    """Forces MJPG to avoid Windows USB bandwidth issues."""
    print(f"[Vision] Connecting to Camera {CAMERA_INDEX}...")
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)
    
    # Simple Warmup loop
    if cap.isOpened():
        try:
            fourcc = cv2.VideoWriter_fourcc(*'MJPG') # type: ignore
        except AttributeError:
            fourcc = cv2.VideoWriter_fourcc(*'MJPG') # type: ignore
        cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        # Warmup Frames
        for _ in range(10):
            cap.read()
        return cap
    return None

def detect_object(frame):
    """
    Finds the largest white blob, BUT applies a mask to ignore window glare.
    Returns: (u, v, angle, annotated_frame)
    """
    h, w = frame.shape[:2]
    
    # --- STEP 1: DEFINE REGION OF INTEREST (ROI) ---
    # Based on your image, we want to ignore the Top ~30% and maybe extreme edges
    mask_roi = np.zeros((h, w), dtype=np.uint8)
    
    # ROI: Start at Y=200 (skip top), End at Y=720 (bottom)
    #      Start at X=200 (skip left wall), End at X=1080 (skip right arm)
    cv2.rectangle(mask_roi, (200, 200), (1080, 720), 255, -1)

    # --- STEP 2: THRESHOLDING ---
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, WHITE_THRESHOLD, 255, cv2.THRESH_BINARY)
    
    # Apply the ROI Mask (Logical AND) - Everything outside ROI becomes Black
    binary = cv2.bitwise_and(binary, binary, mask=mask_roi)

    # Clean noise
    binary = cv2.erode(binary, None, iterations=2) # type: ignore
    binary = cv2.dilate(binary, None, iterations=2) # type: ignore
    
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    vis_frame = frame.copy()
    
    # Draw ROI Box for debugging (Yellow Box)
    cv2.rectangle(vis_frame, (200, 200), (1080, 720), (0, 255, 255), 2)
    
    if contours:
        # Sort by area large to small
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        
        for c in contours:
            area = cv2.contourArea(c)
            
            # Filter by Size (Ignore tiny noise OR massive walls if they sneak in)
            if MIN_AREA < area < MAX_AREA:
                # Calculate Centroid
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    # Draw Success Visuals
                    cv2.drawContours(vis_frame, [c], -1, (0, 255, 0), 2)
                    cv2.circle(vis_frame, (cx, cy), 7, (0, 0, 255), -1)
                    cv2.putText(vis_frame, f"TGT: {cx},{cy}", (cx+10, cy), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    return cx, cy, 0, vis_frame
            
    return None, None, None, vis_frame

def fmt_pose(p):
    return f"p[{p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f}, {p[3]:.4f}, {p[4]:.4f}, {p[5]:.4f}]"

def main():
    print("--- Open-Loop Approach / Closed-Loop Confirmation Test ---")
    
    # 1. Init Hardware
    cap = init_camera_robust()
    if not cap: return
    
    bot_reader = URRobot(ROBOT_IP)
    if not bot_reader.connect(): return
    
    eye = EyeInHand()
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try: sock.connect((ROBOT_IP, PORT_CMD))
    except: print("❌ Socket Failed"); return

    try:
        # --- PHASE 1: SEARCH ---
        print("\n👉 PHASE 1: ACQUIRE TARGET")
        print("   Look for the YELLOW BOX on screen.")
        print("   Only objects INSIDE the box are detected.")
        print("   Press 'SPACE' to Lock Target.")
        
        target_u, target_v = None, None
        search_pose = None
        
        while True:
            ret, frame = cap.read()
            if not ret: continue
            
            u, v, _, vis = detect_object(frame)
            
            if u is not None:
                cv2.putText(vis, "TARGET FOUND", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                target_u, target_v = u, v
            else:
                cv2.putText(vis, "SEARCHING...", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            cv2.imshow("Phase 1: Search", vis)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '):
                if target_u is not None:
                    search_pose = bot_reader.get_tcp_pose()
                    if search_pose:
                        print(f"✅ LOCKED: ({target_u}, {target_v})")
                        break
                    else:
                        print("❌ Failed to read robot pose! Check connection.")
                else:
                    print("❌ No target visible.")
            elif key == ord('q'):
                return

        # Safety Check
        if search_pose is None: return

        # --- PHASE 2: CALCULATE (OPEN LOOP PLAN) ---
        print("\n👉 PHASE 2: CALCULATE & APPROACH")
        
        # 1. World XY
        tx, ty = eye.pixel_to_robot(target_u, target_v, search_pose)
        print(f"   World Target: X={tx:.4f}, Y={ty:.4f}")
        
        # 2. Rotations (Level vs Tilted)
        current_rot = search_pose[3:6]
        
        # Calculate Tilt
        r_curr = R.from_rotvec(current_rot)
        tilt_delta = R.from_euler('x', TILT_ANGLE_DEG, degrees=True)
        r_new = r_curr * tilt_delta
        tilted_rot = r_new.as_rotvec().tolist()
        
        # 3. Construct Script
        script = "def approach_sequence():\n"
        script += f"  textmsg(\"Moving to Hover...\")\n"
        script += f"  movel({fmt_pose([tx, ty, HOVER_Z] + current_rot)}, a=0.3, v=0.1)\n"
        script += f"  textmsg(\"Descending to Grab Height...\")\n"
        script += f"  movel({fmt_pose([tx, ty, GRAB_Z] + current_rot)}, a=0.3, v=0.05)\n"
        script += f"  textmsg(\"Tilting for Confirmation...\")\n"
        script += f"  movel({fmt_pose([tx, ty, GRAB_Z] + tilted_rot)}, a=0.5, v=0.2)\n"
        script += "end\n"
        script += "approach_sequence()\n"
        
        print("🚀 Executing Blind Approach Sequence...")
        sock.sendall(script.encode())
        
        # Wait for motion (approx 8s)
        time.sleep(8.0)
        
        # --- PHASE 3: CLOSED LOOP VERIFICATION ---
        print("\n👉 PHASE 3: VERIFY")
        
        # Flush buffer
        for _ in range(5): cap.read()
        
        while True:
            ret, frame = cap.read()
            if not ret: continue
            
            u, v, _, vis = detect_object(frame)
            
            h, w = frame.shape[:2]
            cx, cy = w//2, h//2
            cv2.line(vis, (cx-20, cy), (cx+20, cy), (255, 255, 0), 2)
            cv2.line(vis, (cx, cy-20), (cx, cy+20), (255, 255, 0), 2)
            
            status = "FAIL"
            color = (0, 0, 255)
            
            if u is not None:
                # Distance from Center of Image
                dist = np.sqrt((u-cx)**2 + (v-cy)**2)
                if dist < 100: 
                    status = "SUCCESS - GRAB READY"
                    color = (0, 255, 0)
                else:
                    status = "OFFSET - CALIB DRIFT?"
                    color = (0, 255, 255)
            
            cv2.putText(vis, f"STATUS: {status}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            cv2.imshow("Phase 3: Verification", vis)
            
            if cv2.waitKey(1) == ord('q'):
                break

    except KeyboardInterrupt:
        print("\nSTOPPING.")
        sock.sendall(b"stopj(2.0)\n")
        
    finally:
        sock.close()
        bot_reader.disconnect()
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
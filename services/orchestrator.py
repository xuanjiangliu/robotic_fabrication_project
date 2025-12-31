import time
import logging
import sys
import os
import cv2
import numpy as np
import requests

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- NEW IMPORTS ---
from pkg.drivers.ur_rtde_wrapper import URRobot, URCapListener
from pkg.vision.eye_in_hand import EyeInHand
from pkg.drivers.sv08_moonraker import MoonrakerClient
from pkg.skills.visual_harvest import VisualHarvester

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
PRINTER_IP = "192.168.50.231"
API_URL = "http://127.0.0.1:5000/api"
CAMERA_INDEX = 1

# Vision Configuration
CAMERA_OFFSET_CFG = "config/camera_offset.json"
WHITE_THRESHOLD = 160
MIN_AREA = 500

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [Orchestrator] - %(message)s')
logger = logging.getLogger()

def detect_object_robust(cap):
    """
    Robust Blob Detection (migrated from test_object_approach.py).
    Returns (u, v) of the target center.
    """
    ret, frame = cap.read()
    if not ret: return None, None

    # ROI Masking (Ignore walls/glare)
    h, w = frame.shape[:2]
    mask_roi = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(mask_roi, (200, 200), (1080, 720), 255, -1)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, WHITE_THRESHOLD, 255, cv2.THRESH_BINARY)
    binary = cv2.bitwise_and(binary, binary, mask=mask_roi)
    
    # Cleanup
    binary = cv2.erode(binary, None, iterations=2) # type: ignore
    binary = cv2.dilate(binary, None, iterations=2) # type: ignore

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contours:
        # Largest blob
        c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(c) > MIN_AREA:
            M = cv2.moments(c)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                return cx, cy

    return None, None

def main():
    logger.info("Initializing RELAY ORCHESTRATOR...")

    # 1. Initialize Systems
    # Client: To read where the robot IS (for vision math)
    robot_monitor = URRobot(ROBOT_IP)
    # Server: To tell the robot where to GO (handshake)
    ur_cap = URCapListener(ip='0.0.0.0', port=50002)
    
    vision = EyeInHand(CAMERA_OFFSET_CFG)
    printer = MoonrakerClient(PRINTER_IP)

    # Initialize Camera
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Connect to RTDE (Monitor)
    if not robot_monitor.connect():
        logger.warning("Could not connect to RTDE Monitor. Vision math may fail.")

    try:
        while True:
            print("\n--- READY FOR HARVEST CYCLE ---")
            print("1. Robot should be moving to 'External Control' node...")
            
            # --- STEP 1: HANDSHAKE (Wait for Robot) ---
            # The robot moves to the "External Control" node and opens a connection.
            # We block here until that happens.
            ur_cap.wait_for_connection()
            
            # --- STEP 2: GET CONTEXT (Pose) ---
            # The robot is now stationary at the "Observation Pose".
            # We flush the camera buffer to get a fresh frame
            for _ in range(5): cap.read()
            
            current_pose = robot_monitor.get_tcp_pose()
            if not current_pose:
                logger.error("Failed to get robot pose via RTDE!")
                ur_cap.close() # Release robot
                continue

            logger.info(f"Robot at Observation Pose: {current_pose}")

            # --- STEP 3: VISION CALCULATION ---
            u, v = detect_object_robust(cap)
            
            if u is None:
                logger.warning("Vision failed: No object found.")
                # We send the robot back to "External Control" or a Safe Home
                # For now, just close connection, robot might error out or skip
                ur_cap.close()
                continue

            # Convert Pixels -> Robot Coordinates (x, y)
            target_x, target_y = vision.pixel_to_robot(u, v, current_pose) #type: ignore
            
            # Construct the Approach Pose
            # We keep the current Z (or set a specific hover Z), Rx, Ry, Rz
            # NOTE: Update '0.15' to your desired approach height if different
            approach_pose = [
                target_x, 
                target_y, 
                current_pose[2], # Maintain current height (or use fixed hover height)
                current_pose[3], 
                current_pose[4], 
                current_pose[5]
            ]
            
            logger.info(f"Target Found at {u},{v}. Approach Vector: {approach_pose}")

            # --- STEP 4: THE RELAY (Send Command) ---
            # We send the move command. The robot executes it, then exits the script,
            # allowing the PolyScope tree to continue to the "Grip" sequence.
            ur_cap.send_move_script(approach_pose, acc=0.8, vel=0.5)

            # --- STEP 5: WAIT FOR CYCLE ---
            # The robot is now executing the local Grip -> Drop loop.
            # We sleep to avoid catching the immediate reconnection if it loops fast.
            time.sleep(5) 

    except KeyboardInterrupt:
        logger.info("Stopping Orchestrator...")
    finally:
        ur_cap.close()
        robot_monitor.disconnect()
        cap.release()

if __name__ == "__main__":
    main()
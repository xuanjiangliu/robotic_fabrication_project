import cv2
import numpy as np
import sys
import os
import time
import csv
import msvcrt
from datetime import datetime

# Setup Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pkg.drivers.camera import Camera
from pkg.drivers.pneumatic_serial import PneumaticSerial
from pkg.vision.analyzer import ActuatorAnalyzer
from pkg.utils.geometry import compute_spine_curvature

# --- CONFIGURATION ---
VALVE_CH = 4
PULSE_MS = 2500        # Slightly longer for drastic change
BASE_LOG_SEC = 2.0     # Zero-baseline state
RECOIL_LOG_SEC = 3.0    # Return-to-zero state
DETECTION_THRESHOLD = 205
ROI_V = [0.35, 0.85]
ROI_H = [0.40, 0.70]
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../logs/trials"))

def get_diagnostics(frame, threshold):
    """Generates mask and ROI coordinates for the HUD."""
    h, w = frame.shape[:2]
    y1, y2 = int(h * ROI_V[0]), int(h * ROI_V[1])
    x1, x2 = int(w * ROI_H[0]), int(w * ROI_H[1])
    
    roi_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(roi_mask, (x1, y1), (x2, y2), 255, -1)
    
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    mask = cv2.bitwise_and(binary, roi_mask)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel), (x1, y1, x2, y2)

def main():
    cam = Camera(camera_index=1); cam.start()
    pneumatic = PneumaticSerial(port="COM5")
    analyzer = ActuatorAnalyzer(threshold=DETECTION_THRESHOLD)
    os.makedirs(LOG_DIR, exist_ok=True)
    
    with open("config/camera_offset.json", 'r') as f:
        import json
        ppm = json.load(f).get("pixels_per_meter", 1916.2)

    print("\n[STEP 1] ALIGNMENT: Adjust PneuNet so Red Mask is clear.")
    while True:
        _, frame = cam.get_frames()
        if frame is None: continue
        mask, roi = get_diagnostics(frame, DETECTION_THRESHOLD)
        preview = frame.copy()
        cv2.rectangle(preview, (roi[0], roi[1]), (roi[2], roi[3]), (0, 255, 255), 2)
        preview[mask > 0] = [0, 0, 255] # Red Area Restored
        cv2.imshow("RoboFab: Alignment", preview)
        if cv2.waitKey(1) & 0xFF == 13 or (msvcrt.kbhit() and msvcrt.getch() in [b'\r', b'\n']):
            break

    # --- TRIAL LOGGING ---
    log_file = os.path.join(LOG_DIR, f"3state_trial_{datetime.now().strftime('%H%M%S')}.csv")
    with open(log_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["time_sec", "mean_k", "state"])
        
        start_t = time.time(); pulse_triggered = False
        total_time = BASE_LOG_SEC + (PULSE_MS/1000.0) + RECOIL_LOG_SEC

        try:
            while (time.time() - start_t) < total_time:
                elapsed = time.time() - start_t
                _, frame = cam.get_frames()
                mask, roi = get_diagnostics(frame, DETECTION_THRESHOLD)
                skeleton = analyzer.extract_spine(mask)
                res = compute_spine_curvature(skeleton, ppm)
                
                # Determine State
                if elapsed < BASE_LOG_SEC: state = "DEFLATED_BASE"
                elif elapsed < (BASE_LOG_SEC + PULSE_MS/1000.0):
                    state = "INFLATING"
                    if not pulse_triggered: pneumatic.start_pulse(VALVE_CH, PULSE_MS); pulse_triggered = True
                else: state = "RECOIL_DEFLATING"

                writer.writerow([elapsed, res.mean_curvature, state])

                # HUD
                display = frame.copy() # type: ignore
                cv2.rectangle(display, (roi[0], roi[1]), (roi[2], roi[3]), (0, 255, 255), 2)
                display[mask > 0] = [0, 0, 255] # Red mask
                display[skeleton > 0] = [0, 255, 0] # Green spine
                cv2.putText(display, f"STATE: {state}", (10, 40), 1, 1.8, (0, 255, 255), 2)
                cv2.putText(display, f"K: {res.mean_curvature:.4f}", (10, 80), 1, 1.5, (0, 255, 0), 2)
                cv2.imshow("RoboFab: Alignment", display); cv2.waitKey(1)

        finally:
            pneumatic.close(); cam.stop(); cv2.destroyAllWindows()
            print(f"✅ Trial saved to {log_file}")

if __name__ == "__main__":
    main()
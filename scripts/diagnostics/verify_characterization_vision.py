import cv2
import numpy as np
import sys
import os
import time
import csv
import msvcrt 
from datetime import datetime
from collections import deque

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pkg.drivers.camera import Camera
from pkg.vision.analyzer import ActuatorAnalyzer 
from pkg.utils.geometry import compute_spine_curvature

# --- ROI & THRESHOLD CONFIGURATION ---
ROI_V = [0.35, 0.85]  # Middle vertical
ROI_H = [0.40, 0.75]  # Middle horizontal
DETECTION_THRESHOLD = 205 
LOG_WINDOW = 5        # Smoothing window for the graph

def get_roi_mask(frame, threshold):
    """Isolates central pneunet and filters background noise."""
    h, w = frame.shape[:2]
    roi_mask = np.zeros((h, w), dtype=np.uint8)
    y1, y2 = int(h * ROI_V[0]), int(h * ROI_V[1])
    x1, x2 = int(w * ROI_H[0]), int(w * ROI_H[1])
    cv2.rectangle(roi_mask, (x1, y1), (x2, y2), 255, -1)
    
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    final_mask = cv2.bitwise_and(binary, roi_mask)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    return cv2.morphologyEx(final_mask, cv2.MORPH_OPEN, kernel), (x1, y1, x2, y2)

def main():
    print("--- Diagnostic: Robust 2D Curvature (No-Depth Mode) ---")
    
    cam = Camera(camera_index=1)
    if not cam.start(): return

    analyzer = ActuatorAnalyzer()
    os.makedirs("logs/characterization", exist_ok=True)
    log_file = f"logs/characterization/curvature_log_{datetime.now().strftime('%H%M%S')}.csv"
    
    # Load PPM from config
    calib_data = cam.load_intrinsics("config/camera_offset.json")
    ppm = 1916.2 # Default from your config if loading fails
    with open("config/camera_offset.json", 'r') as f:
        import json
        ppm = json.load(f).get("pixels_per_meter", ppm)

    k_buffer = deque(maxlen=LOG_WINDOW)

    print("\n[STEP 1] Preview Mode: Center the PneuNet.")
    print("👉 Press ENTER to start logging...")
    
    while True:
        _, frame = cam.get_frames()
        if frame is None: continue
        mask, roi = get_roi_mask(frame, DETECTION_THRESHOLD)
        preview = frame.copy()
        cv2.rectangle(preview, (roi[0], roi[1]), (roi[2], roi[3]), (0, 255, 255), 2)
        preview[mask > 0] = [0, 0, 255]
        cv2.imshow("Vision Verification", preview)
        if cv2.waitKey(1) & 0xFF == 13 or (msvcrt.kbhit() and msvcrt.getch() in [b'\r', b'\n']):
            break

    print(f"\n[STEP 2] Logging to: {log_file}")
    with open(log_file, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "mean_curvature", "radius_mm", "status"])

        try:
            while True:
                _, frame = cam.get_frames()
                if frame is None: continue

                mask, _ = get_roi_mask(frame, DETECTION_THRESHOLD)
                skeleton = analyzer.extract_spine(mask)
                
                # Robust Circle Fit (No-Depth Algorithm)
                res = compute_spine_curvature(skeleton, None, ppm) # type: ignore

                # Smoothing Filter
                if res.status == "TRACKING":
                    k_buffer.append(res.mean_curvature)
                smoothed_k = np.mean(k_buffer) if k_buffer else 0.0

                # UI
                display = frame.copy()
                display[mask > 0] = [0, 0, 255]
                display[skeleton > 0] = [0, 255, 0]
                cv2.putText(display, f"K: {smoothed_k:.4f} (1/m)", (10, 30), 1, 1.5, (0, 255, 0), 2)
                cv2.putText(display, f"R: {res.radius_mm:.1f} mm", (10, 60), 1, 1.2, (255, 255, 255), 1)
                
                writer.writerow([time.time(), smoothed_k, res.radius_mm, res.status]) 
                cv2.imshow("Vision Verification", display)
                if cv2.waitKey(1) & 0xFF == ord('q'): break

        finally:
            cam.stop(); cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
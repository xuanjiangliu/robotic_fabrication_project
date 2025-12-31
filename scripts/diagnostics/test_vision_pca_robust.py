import sys
import os
import cv2
import numpy as np

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# We duplicate the analysis logic here slightly to allow dynamic thresholding
# without breaking the main library file yet.

def analyze_with_threshold(image, thresh_val):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply dynamic threshold from slider
    _, thresh = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY_INV)
    
    # Find Contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return None, thresh # Return thresh for debug view
        
    # Get Largest Blob
    c = max(contours, key=cv2.contourArea)
    if cv2.contourArea(c) < 500: 
        return None, thresh

    # Moments
    M = cv2.moments(c)
    if M["m00"] == 0: return None, thresh
    cx = int(M["m10"] / M["m00"])
    cy = int(M["m01"] / M["m00"])

    # PCA
    sz = len(c)
    data_pts = np.empty((sz, 2), dtype=np.float64)
    for i in range(data_pts.shape[0]):
        data_pts[i,0] = c[i,0,0]
        data_pts[i,1] = c[i,0,1]
    
    mean = np.empty((0))
    mean, eigenvectors, _ = cv2.PCACompute2(data_pts, mean)
    angle = np.arctan2(eigenvectors[0,1], eigenvectors[0,0])
    
    return (cx, cy, angle), thresh

def nothing(x):
    pass

def main():
    print("--- Robust Vision PCA Test ---")
    print("Adjust the slider until only your part is white!")
    print("Press 'q' to quit.")
    
    # 1. Open Camera
    cap = cv2.VideoCapture(1, cv2.CAP_MSMF)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    # 2. Create Window & Slider
    cv2.namedWindow("Vision PCA")
    cv2.createTrackbar("Threshold", "Vision PCA", 100, 255, nothing)

    while True:
        ret, frame = cap.read()
        if not ret: continue
        
        # Get slider value
        th_val = cv2.getTrackbarPos("Threshold", "Vision PCA")
        
        # Run Analysis
        result, debug_thresh = analyze_with_threshold(frame, th_val)
        
        # Draw on original
        display = frame.copy()
        
        if result:
            cx, cy, angle = result
            
            # Draw Axis
            length = 100
            end_x = int(cx + length * np.cos(angle))
            end_y = int(cy + length * np.sin(angle))
            cv2.line(display, (cx, cy), (end_x, end_y), (0, 0, 255), 3)
            cv2.circle(display, (cx, cy), 5, (0, 255, 0), -1)
            
            # Draw Text
            deg = np.degrees(angle)
            cv2.putText(display, f"Angle: {deg:.1f}", (cx + 20, cy), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        
        # Show both windows (Real view + What the computer sees)
        # We stack them roughly or show separate
        cv2.imshow("Vision PCA", display)
        cv2.imshow("Mask (Debug)", debug_thresh)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print(f"✅ Final Threshold Value: {th_val}")
            print(f"👉 Please update pkg/vision/analysis.py with this value!")
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
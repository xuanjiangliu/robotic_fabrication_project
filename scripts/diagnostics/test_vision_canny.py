import sys
import os
import cv2
import numpy as np

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

def nothing(x):
    pass

def main():
    print("--- Canny Edge Tuning ---")
    print("1. Slide 'Min' and 'Max' to isolate the Benchy outline.")
    print("2. 'Dilate' makes the lines thicker to connect gaps.")
    print("Press 'q' to Quit.")

    # Open Camera
    cap = cv2.VideoCapture(1, cv2.CAP_MSMF)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    cv2.namedWindow("Tuner")
    cv2.createTrackbar("Canny Min", "Tuner", 50, 255, nothing)
    cv2.createTrackbar("Canny Max", "Tuner", 100, 255, nothing)
    cv2.createTrackbar("Dilate Iter", "Tuner", 1, 5, nothing)

    while True:
        ret, frame = cap.read()
        if not ret: continue
        
        # 1. Pre-process
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 2. Get Slider Values
        min_val = cv2.getTrackbarPos("Canny Min", "Tuner")
        max_val = cv2.getTrackbarPos("Canny Max", "Tuner")
        dil_iter = cv2.getTrackbarPos("Dilate Iter", "Tuner")

        # 3. Canny
        edges = cv2.Canny(blurred, min_val, max_val)

        # 4. Dilate
        kernel = np.ones((5,5), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=dil_iter)

        # 5. Find Contours (Visualization only)
        display = frame.copy()
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Draw all contours found
        cv2.drawContours(display, contours, -1, (0, 255, 0), 2)
        
        # Show largest PCA
        if contours:
            c = max(contours, key=cv2.contourArea)
            if cv2.contourArea(c) > 1000:
                # Calculate center
                M = cv2.moments(c)
                if M["m00"] != 0:
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
                    
                    # Draw Axis
                    length = 100
                    end_x = int(cx + length * np.cos(angle))
                    end_y = int(cy + length * np.sin(angle))
                    cv2.line(display, (cx, cy), (end_x, end_y), (0, 0, 255), 4)

        # Stack images for display
        # Convert edges to BGR so we can stack them
        edges_bgr = cv2.cvtColor(dilated, cv2.COLOR_GRAY2BGR)
        combined = np.hstack((display, edges_bgr))
        
        # Resize to fit screen
        scale = 0.5
        h, w = combined.shape[:2]
        small = cv2.resize(combined, (int(w*scale), int(h*scale)))

        cv2.imshow("Tuner", small)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print(f"✅ Final Settings -> Min: {min_val}, Max: {max_val}, Dilate: {dil_iter}")
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
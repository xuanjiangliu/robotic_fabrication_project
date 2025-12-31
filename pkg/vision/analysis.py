import cv2
import numpy as np

# --- CONFIGURATION ---
# Robust settings for Black Benchy on White Bed
CANNY_LOW = 150   # High enough to ignore bed texture
CANNY_HIGH = 255  # Requires strong contrast
MIN_AREA = 1000   # Ignored small specs

def find_part_alignment(image):
    """
    Robustly finds the part using Edge Detection (Canny).
    Returns: (center_u, center_v, angle_rad, success_bool)
    """
    # 1. Pre-process
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Blur is CRITICAL for Canny to ignore 3D print layer lines
    blurred = cv2.GaussianBlur(gray, (9, 9), 0) 
    
    # 2. Edge Detection (Canny)
    edges = cv2.Canny(blurred, CANNY_LOW, CANNY_HIGH)
    
    # 3. Dilate (Close gaps)
    # We use 2 iterations to make sure the outline is solid
    kernel = np.ones((5,5), np.uint8)
    dilated_edges = cv2.dilate(edges, kernel, iterations=2)
    
    # 4. Find Contours
    contours, _ = cv2.findContours(dilated_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return 0, 0, 0, False
        
    # 5. Filter: Find Largest Valid Blob
    valid_contour = None
    # Sort by area so we check the biggest blobs first
    sorted_contours = sorted(contours, key=cv2.contourArea, reverse=True)
    
    for c in sorted_contours:
        if cv2.contourArea(c) > MIN_AREA:
            valid_contour = c
            break
            
    if valid_contour is None:
        return 0, 0, 0, False

    # 6. Center (Moments)
    M = cv2.moments(valid_contour)
    if M["m00"] == 0: return 0, 0, 0, False
    cx = int(M["m10"] / M["m00"])
    cy = int(M["m01"] / M["m00"])

    # 7. Orientation (PCA)
    sz = len(valid_contour)
    data_pts = np.empty((sz, 2), dtype=np.float64)
    for i in range(data_pts.shape[0]):
        data_pts[i,0] = valid_contour[i,0,0]
        data_pts[i,1] = valid_contour[i,0,1]
    
    mean = np.empty((0))
    mean, eigenvectors, _ = cv2.PCACompute2(data_pts, mean)
    angle = np.arctan2(eigenvectors[0,1], eigenvectors[0,0])
    
    return cx, cy, angle, True
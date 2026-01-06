# pkg/utils/geometry.py
import numpy as np
from scipy.interpolate import splprep, splev
from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class Point:
    """A simple data class for a 3D point."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

@dataclass
class CurvatureResult:
    """Holds the results of a curvature analysis."""
    mean_curvature: float = 0.0
    max_curvature: float = 0.0
    spline_points: List[Point] = field(default_factory=list)

def compute_spine_curvature(skeleton_mask: np.ndarray, depth_image: np.ndarray,
                            intrinsics: np.ndarray, depth_scale: float,
                            base_angle_deg: float = 60.0) -> CurvatureResult:
    """
    Fits a 3D spline to the pneunet spine, accounting for its 60-degree tilt.
    
    Args:
        base_angle_deg: The mounting angle relative to the X-axis. 
                        60 deg "up" assumes a vector of (cos60, -sin60).
    """
    # 1. Extract 2D skeleton pixels
    v, u = np.where(skeleton_mask > 0)
    z = depth_image[v, u] * depth_scale
    
    # Filter valid depth points
    valid = z > 0
    u, v, z = u[valid], v[valid], z[valid]
    
    if len(z) < 20: 
        return CurvatureResult()

    # 2. Back-project to 3D Camera Space
    fx, fy = intrinsics[0, 0], intrinsics[1, 1]
    cx, cy = intrinsics[0, 2], intrinsics[1, 2]
    x = (u - cx) * z / fx
    y = (v - cy) * z / fy
    pcd = np.vstack((x, y, z)).transpose()

    try:
        # 3. Directional Projection Sort
        # We project points onto the base-to-tip vector of the un-inflated pneunet.
        # This ensures points are always ordered from base to tip.
        theta = np.radians(base_angle_deg)
        # Vector pointing 'up' at 60 degrees (-Y is up in camera space)
        direction_vec = np.array([np.cos(theta), -np.sin(theta), 0])
        
        projections = pcd @ direction_vec
        sorted_indices = np.argsort(projections)
        sorted_pcd = pcd[sorted_indices]
        
        # 4. Fit 3D Parametric Spline
        # s=0.01 provides smoothing for depth sensor noise
        tck, _ = splprep([sorted_pcd[:, 0], sorted_pcd[:, 1], sorted_pcd[:, 2]], s=0.01, k=3)
        
        # 5. Calculate Curvature (kappa = |r' x r''| / |r'|^3)
        # Derived from existing robust derivatives logic
        u_fine = np.linspace(0, 1, 100)
        r_prime = np.array(splev(u_fine, tck, der=1))
        r_double_prime = np.array(splev(u_fine, tck, der=2))

        cross = np.cross(r_prime.T, r_double_prime.T)
        curvature = np.linalg.norm(cross, axis=1) / (np.linalg.norm(r_prime, axis=0)**3)
        
        # 6. Generate Spline Points for Visualization
        spline_np = np.array(splev(u_fine, tck)).T
        spline_points = [Point(x=p[0], y=p[1], z=p[2]) for p in spline_np]
        
        return CurvatureResult(
            mean_curvature=float(np.mean(curvature)),
            max_curvature=float(np.max(curvature)),
            spline_points=spline_points
        )
    except Exception:
        return CurvatureResult()
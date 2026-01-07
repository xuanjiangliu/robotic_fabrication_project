# pkg/utils/geometry.py
import numpy as np
from dataclasses import dataclass

@dataclass
class CurvatureResult:
    mean_curvature: float = 0.0
    radius_mm: float = 0.0
    status: str = "IDLE"

def compute_spine_curvature(skeleton_mask: np.ndarray, ppm: float) -> CurvatureResult:
    """Calculates metric curvature by fitting a circle to the flexible spine section."""
    v, u = np.where(skeleton_mask > 0)
    
    if len(u) < 60: 
        return CurvatureResult(status="NO_TARGET")

    # RESEARCH FIX: Sort pixels from base to tip and trim the rigid mounting base
    # This prevents the 'base' from biasing the circle into a permanent curve.
    idx = np.argsort(v)[::-1] # Bottom to top
    u_flex = u[idx][40:] 
    v_flex = v[idx][40:]

    if len(u_flex) < 20: return CurvatureResult(status="TOO_SHORT")

    # Least Squares Circle Fit
    u_m, v_m = np.mean(u_flex), np.mean(v_flex)
    u_c, v_c = u_flex - u_m, v_flex - v_m
    A = np.column_stack([u_c, v_c, np.ones_like(u_c)])
    b = u_c**2 + v_c**2
    
    try:
        C, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
        radius_px = np.sqrt(C[2] + (C[0]/2)**2 + (C[1]/2)**2)
        radius_m = radius_px / ppm
        
        return CurvatureResult(
            mean_curvature=1.0 / radius_m, 
            radius_mm=radius_m * 1000.0, 
            status="TRACKING"
        )
    except Exception:
        return CurvatureResult(status="MATH_ERROR")
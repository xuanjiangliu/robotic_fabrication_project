import json
import logging
import numpy as np
import os

class SpatialManager:
    def __init__(self, cage_file="config/printer_cage.json"):
        self.logger = logging.getLogger("RoboFab.Spatial")
        self.cage_active = False
        self.cage = {}
        self.entry_pose = None
        
        # Load Cage
        if os.path.exists(cage_file):
            try:
                with open(cage_file, 'r') as f:
                    raw_data = json.load(f)
                
                # Sort min/max to ensure mathematical correctness
                # (e.g., if user taught x_min as 0.5 and x_max as -0.5, we fix it)
                self.cage = {
                    'x': sorted([raw_data.get('x_min', -0.5), raw_data.get('x_max', 0.5)]),
                    'y': sorted([raw_data.get('y_min', -0.5), raw_data.get('y_max', -0.2)]),
                    'z': sorted([raw_data.get('z_min', 0.0), raw_data.get('z_max', 0.5)])
                }
                
                # Load Explicit Entry Pose if available
                if 'entry_pose' in raw_data:
                    self.entry_pose = raw_data['entry_pose']
                
                self.cage_active = True
                self.logger.info(f"✅ Safety Cage Loaded. Entry Pose: {self.entry_pose is not None}")
                
            except Exception as e:
                self.logger.error(f"❌ Failed to load cage file: {e}")
        else:
            self.logger.warning(f"⚠️ Cage file {cage_file} not found! Safety checks DISABLED.")

    def is_in_cage(self, point):
        """ Checks if a [x,y,z] point is strictly inside the cage. """
        if not self.cage_active: return True 

        x, y, z = point[0], point[1], point[2]
        return (self.cage['x'][0] <= x <= self.cage['x'][1] and
                self.cage['y'][0] <= y <= self.cage['y'][1] and
                self.cage['z'][0] <= z <= self.cage['z'][1])

    def clamp_target(self, current_pose, target_offset):
        """
        Takes current pose and offset (dx, dy, dz).
        Returns a SAFE absolute target coordinate [x, y, z].
        """
        tx = current_pose[0] + target_offset[0]
        ty = current_pose[1] + target_offset[1]
        tz = current_pose[2] + target_offset[2]

        if not self.cage_active:
            return [tx, ty, tz]

        # Clamp to boundaries
        safe_x = max(self.cage['x'][0], min(tx, self.cage['x'][1]))
        safe_y = max(self.cage['y'][0], min(ty, self.cage['y'][1]))
        safe_z = max(self.cage['z'][0], min(tz, self.cage['z'][1]))

        if abs(safe_x - tx) > 0.001 or abs(safe_y - ty) > 0.001 or abs(safe_z - tz) > 0.001:
             # Just a debug print to reduce log spam
             # print(f"Clamp: [{tx:.2f},{ty:.2f},{tz:.2f}] -> [{safe_x:.2f},{safe_y:.2f},{safe_z:.2f}]")
             pass

        return [safe_x, safe_y, safe_z]

    def get_entry_pose(self):
        """
        Returns the EXPLICITLY taught entry pose [x,y,z,rx,ry,rz].
        """
        if self.entry_pose:
            return self.entry_pose
        
        # Fallback if no entry pose taught: Calculate geometric center of door
        if self.cage_active:
            center_x = (self.cage['x'][0] + self.cage['x'][1]) / 2.0
            center_z = (self.cage['z'][0] + self.cage['z'][1]) / 2.0
            # Assume Y_Max is the door
            entry_y = self.cage['y'][1] 
            # Default rotation (pointing down-ish) - purely a guess
            return [center_x, entry_y, center_z, 2.2, -2.2, 0.0]
            
        return None
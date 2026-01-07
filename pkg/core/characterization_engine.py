import time
import os
import csv
import logging
from abc import ABC, abstractmethod
from enum import Enum, auto
from datetime import datetime

# Import existing modules based on repository structure
from pkg.drivers.camera import Camera
from pkg.drivers.pneumatic_serial import PneumaticSerial
from pkg.vision.analyzer import ActuatorAnalyzer
from pkg.utils.geometry import compute_spine_curvature

class EngineState(Enum):
    IDLE = auto()
    BASELINE = auto()
    INFLATING = auto()
    RECOIL = auto()
    ERROR = auto()

class BaseCharacterizationEngine(ABC):
    def __init__(self, camera_idx=1, pneu_port="COM5", ppm=1916.2):
        self.logger = logging.getLogger("RoboFab.Engine")
        self.ppm = ppm
        self.state = EngineState.IDLE
        
        # Initialize Hardware Drivers
        self.cam = Camera(camera_index=camera_idx)
        self.pneumatic = PneumaticSerial(port=pneu_port)
        self.analyzer = ActuatorAnalyzer() 
        
        # Ensure log directory exists
        self.log_dir = "logs/trials"
        os.makedirs(self.log_dir, exist_ok=True)

    def setup(self):
        """Standard hardware startup sequence."""
        if not self.cam.start():
            self.state = EngineState.ERROR
            return False
        self.logger.info("✅ Characterization Engine Ready.")
        return True

    @abstractmethod
    def process_frame(self, frame):
        """Vision logic to be implemented by specific engine types."""
        pass

    def run_trial(self, channel: int, duration_ms: int, label: str = "trial"):
        """
        The Automated 3-State Loop.
        State 1: Baseline (2s)
        State 2: Inflation (Timed pulse)
        State 3: Recoil (3s)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.log_dir, f"{label}_{timestamp}.csv")
        
        start_time = time.time()
        pulse_triggered = False
        
        # Timing constants
        baseline_duration = 2.0
        recoil_duration = 3.0
        total_trial_time = baseline_duration + (duration_ms / 1000.0) + recoil_duration

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "elapsed", "state", "curvature_k"])

            try:
                while (time.time() - start_time) < total_trial_time:
                    elapsed = time.time() - start_time
                    _, frame = self.cam.get_frames() #
                    
                    if frame is None: continue

                    # 1. Update Internal State
                    if elapsed < baseline_duration:
                        self.state = EngineState.BASELINE
                    elif elapsed < (baseline_duration + duration_ms / 1000.0):
                        self.state = EngineState.INFLATING
                        if not pulse_triggered:
                            self.pneumatic.start_pulse(channel, duration_ms) #
                            pulse_triggered = True
                    else:
                        self.state = EngineState.RECOIL

                    # 2. Vision Pipeline
                    result = self.process_frame(frame)
                    
                    # 3. Log Data
                    writer.writerow([time.time(), elapsed, self.state.name, result])
                    
                    # 4. Mandatory HUD
                    self.render_hud(frame, result)
                    
            finally:
                self.state = EngineState.IDLE
                self.cleanup_trial()

    def cleanup_trial(self):
        """Reset peripherals after a run."""
        self.pneumatic.abort() 

        import cv2
        cv2.destroyAllWindows()

    @abstractmethod
    def render_hud(self, frame, result):
        """Maintain the Diagnostic HUD during the run."""
        pass
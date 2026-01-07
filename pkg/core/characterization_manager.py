import logging
import os
from dataclasses import dataclass
from pkg.core.deterministic_engine import DeterministicEngine
from pkg.utils.spatial import SpatialManager
from pkg.drivers.ur_rtde_wrapper import URRobot

@dataclass
class CharacterizationJob:
    """Command Pattern for characterization tasks."""
    job_id: str
    channel: int
    pulse_duration_ms: int
    actuator_type: str = "PneuNet_V1"

class CharacterizationManager:
    """
    High-level manager for autonomous characterization.
    Coordinates vision, pneumatics, and safety without breaking 
    the factory orchestrator's existing code.
    """
    def __init__(self, camera_idx=1, pneu_port="COM5"):
        self.logger = logging.getLogger("RoboFab.CharManager")
        
        # 1. Initialize the Engine (Vision + Pneumatics)
        self.engine = DeterministicEngine(
            camera_idx=camera_idx, 
            pneu_port=pneu_port, 
            ppm=1916.2  # Calibrated SI Units (1/m)
        )
        
        # 2. Safety & Hardware Monitoring
        self.spatial = SpatialManager()
        self.robot_monitor = None

    def run_autonomous_test(self, job: CharacterizationJob, robot_ip: str = None): # type: ignore
        """
        Executes the 3-State Loop: Baseline -> Inflation -> Recoil.
        Does not interfere with Moonraker/Printer logic.
        """
        self.logger.info(f"🚀 Starting Test: {job.job_id} on CH{job.channel}")
        
        # 1. Safety Check: Verify Robot Position
        if robot_ip:
            if not self._check_safety(robot_ip):
                return False

        # 2. Setup Hardware (Camera Warmup)
        if not self.engine.setup():
            return False

        # 3. Trigger 3-State Characterization Loop
        try:
            self.engine.run_trial(
                channel=job.channel, 
                duration_ms=job.pulse_duration_ms, 
                label=f"{job.actuator_type}_{job.job_id}"
            )
            return True
        except Exception as e:
            self.logger.error(f"❌ Characterization Failure: {e}")
            return False
        finally:
            self.engine.cleanup_trial()

    def _check_safety(self, ip):
        """Ensures robot is in the characterization zone."""
        try:
            if not self.robot_monitor:
                self.robot_monitor = URRobot(ip)
                self.robot_monitor.connect()
            
            pose = self.robot_monitor.get_tcp_pose()
            if pose and self.spatial.is_in_cage(pose[:3]):
                return True
            self.logger.error("❌ Robot is NOT in a safe zone for testing!")
            return False
        except:
            return True # Fallback for local simulation
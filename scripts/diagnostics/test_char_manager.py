import sys
import os
import logging
import time

# Ensure the root directory is in the path so we can import our new core modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pkg.core.characterization_manager import CharacterizationManager, CharacterizationJob

# Setup Logging for the test
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(name)s - %(message)s'
)
logger = logging.getLogger("CharManagerTest")

def main():
    logger.info("Initializing Characterization Manager Test...")

    # 1. Initialize the Manager 
    # Adjust port and camera_idx as per your diagnostic tests (e.g., COM5, ID 1)
    manager = CharacterizationManager(camera_idx=1, pneu_port="COM5")

    # 2. Define a Test Job
    # This job simulates a 2.0 second pulse on Channel 4
    test_job = CharacterizationJob(
        job_id="UNIT_TEST_001",
        channel=4,
        pulse_duration_ms=2000,
        actuator_type="Test_PneuNet"
    )

    # 3. Execution
    print("\n" + "="*50)
    print("🚀 READINESS CHECK")
    print("1. Ensure Orbbec Camera is connected.")
    print("2. Ensure Arduino is on COM5 and PneuNet is connected to CH4.")
    print("3. Ensure the actuator is within the Yellow ROI in the HUD.")
    print("="*50)
    input("PRESS ENTER TO START 3-STATE CHARACTERIZATION...")

    try:
        # We run without robot_ip for this standalone test to focus on vision/pneumatics
        success = manager.run_autonomous_test(test_job)
        
        if success:
            logger.info("✅ Test Loop Completed Successfully.")
            print("\nVerification Checklist:")
            print("- [ ] Did the HUD show a Red Mask and Green Spine?")
            print("- [ ] Did the Arduino pulse for 2 seconds?")
            print("- [ ] Is there a new CSV file in 'logs/trials/'?")
        else:
            logger.error("❌ Test Loop Failed. Check logs for details.")

    except KeyboardInterrupt:
        logger.warning("🛑 Test aborted by user.")
    finally:
        logger.info("Cleaning up...")
        # The manager handles internal cleanup (pneumatic abort) via its finally block

if __name__ == "__main__":
    main()
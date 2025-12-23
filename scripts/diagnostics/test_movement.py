import sys
import os
import time
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.drivers.ur_rtde_wrapper import URRobot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RobotTest")

ROBOT_IP = "192.168.50.82" 

def test_robot():
    # 1. Use correct Class Name
    bot = URRobot(ROBOT_IP)
    
    logger.info(f"Connecting to {ROBOT_IP}...")
    if not bot.connect():
        logger.error("Failed to connect.")
        return

    # --- DIAGNOSTICS START ---
    logger.info("--- ROBOT STATUS CHECK ---")
    
    # 2. Get Joint Angles (The "Eyes")
    current_joints = bot.get_joint_angles()
    logger.info(f"Current Joints: {current_joints}")

    if current_joints is None:
        logger.error("Critical: Could not read joint angles.")
        return

    # 3. Prepare Move
    target_joints = list(current_joints)
    target_joints[0] += 0.1 

    print("\nWARNING: Robot BASE will rotate ~6 degrees. Hand on E-STOP?")
    # input("Press Enter to execute move...") # Uncomment for safety pause

    logger.info("Sending move_j command...")
    start_time = time.time()
    
    # 4. Execute Move (The "Hands")
    # Changed from 'move_joint' to 'move_j'
    bot.move_j(target_joints, speed=0.2, acceleration=0.2)
    
    # Wait for motion to start (Socket latency)
    time.sleep(0.5)
    
    # Monitor Motion
    while bot.is_moving():
        logger.info(f"Robot Moving... Speed: {bot.get_joint_speeds()[0]:.4f}")
        time.sleep(0.2)

    duration = time.time() - start_time
    logger.info(f"Move sequence finished in {duration:.2f} seconds.")

    bot.disconnect()

if __name__ == "__main__":
    test_robot()
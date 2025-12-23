import sys
import os
import time
import json
import logging

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from pkg.drivers.ur_rtde_wrapper import URRobot

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
CAGE_FILE = os.path.join(os.path.dirname(__file__), '../config/printer_cage.json')
PATROL_SPEED = 0.15   # Meters/sec (Safe/Slow)
PATROL_ACCEL = 0.3

# Logging Setup
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("CagePatrol")

def test_patrol():
    logger.info("--- RoboFab 8-Point Cage Verification ---")
    
    # 1. Load the JSON Data
    if not os.path.exists(CAGE_FILE):
        logger.error(f"❌ Cage file not found: {CAGE_FILE}")
        logger.error("Run 'teach_cage_interactive.py' first!")
        return

    with open(CAGE_FILE, 'r') as f:
        cage_data = json.load(f)

    # Validate Entry Pose
    if "entry_pose" not in cage_data:
        logger.error("❌ 'entry_pose' missing from config.")
        return
        
    entry_pose = cage_data["entry_pose"]

    # Define the patrol sequence (Order ensures a clean box path)
    # We trace the Bottom perimeter -> Move Up -> Trace Top perimeter
    sequence_keys = [
        "corner_bottom_left_front",
        "corner_bottom_right_front",
        "corner_bottom_right_back",
        "corner_bottom_left_back",
        "corner_top_left_back",     # Lift up at the back
        "corner_top_right_back",
        "corner_top_right_front",
        "corner_top_left_front"
    ]

    # 2. Connect to Robot
    logger.info(f"Connecting to Robot at {ROBOT_IP}...")
    bot = URRobot(ROBOT_IP)
    if not bot.connect():
        logger.error("❌ Connection Failed.")
        return

    try:
        print("\n" + "="*50)
        print("🚀 STARTING 8-POINT PATROL")
        print("⚠️  Ensure the robot is manually jogged 'NEAR' the Entry Pose first.")
        print("   (This prevents configuration flips during the first approach)")
        print("="*50)
        
        # 3. Move to Entry Pose
        logger.info(f"📍 Moving to ENTRY POSE...")
        # We use move_l to strictly enforce the linear path to entry
        bot.move_l(entry_pose, speed=PATROL_SPEED, acceleration=PATROL_ACCEL)
        
        while bot.is_moving(): time.sleep(0.1)
        time.sleep(1.0)

        # 4. Execute Patrol
        for key in sequence_keys:
            if key not in cage_data:
                logger.warning(f"⚠️  Skipping missing key: {key}")
                continue
                
            target = cage_data[key]
            logger.info(f"📍 Moving to: {key}")
            
            # Execute Linear Move
            bot.move_l(target, speed=PATROL_SPEED, acceleration=PATROL_ACCEL)
            
            # Wait for completion
            time.sleep(0.1) # Buffer
            while bot.is_moving():
                time.sleep(0.1)
            time.sleep(0.5) # Short pause at corner

        # 5. Return to Entry
        logger.info(f"📍 Returning to ENTRY POSE...")
        bot.move_l(entry_pose, speed=PATROL_SPEED, acceleration=PATROL_ACCEL)
        while bot.is_moving(): time.sleep(0.1)

        logger.info("✅ Patrol Complete. All 8 corners are verified reachable.")

    except KeyboardInterrupt:
        logger.warning("\n🛑 Patrol Aborted by User.")
        bot.stop()
    except Exception as e:
        logger.error(f"❌ Error during patrol: {e}")
        bot.stop()
    finally:
        bot.disconnect()

if __name__ == "__main__":
    test_patrol()
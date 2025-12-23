import time
import logging
import sys
import os

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pkg.drivers.ur_rtde_wrapper import URRobot
from pkg.drivers.sv08_moonraker import MoonrakerClient

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
PRINTER_IP = "192.168.50.231"
BED_COOLDOWN_TARGET = 60.0

# --- WAYPOINTS (RESTORED FROM HANDOVER) ---
# Home Position
HOME_JOINTS = [-1.7648, -1.8919, -1.9362, 0.9878, 1.7430, -3.0181]

# Approach Waypoints
PRE_GRASP_JOINTS = [-1.6659, -2.6448, -1.4209, 0.8461, 1.7655, -3.1746]

# Grasp Pose (Linear Approach)
GRASP_POSE_L = [-0.15626, -0.97918, 0.03216, 2.38075, 0.02521, 0.05867]

# Safety Exit (Clear of Enclosure)
EXIT_JOINTS = [-1.6892, -2.2191, -2.0807, 0.8998, 1.8837, -3.2554]

# Drop Zone (Bin)
DROP_JOINTS = [-2.0018, -2.3456, -2.4387, 1.0555, 0.8318, -2.5799]

# --- SETUP LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [RoboFab] - %(message)s')
logger = logging.getLogger()

def main():
    logger.info("Initializing RoboFab Workcell (Modbus Mode)...")

    bot = URRobot(ROBOT_IP)
    printer = MoonrakerClient(PRINTER_IP)

    # 1. CONNECT & CHECK GRIPPER
    # This replaces the old "wait_and_reconnect" and "driver_loop" checks.
    # The connect() method now handles the Modbus activation internally.
    if not bot.connect():
        logger.error("CRITICAL: Robot Connection Failed. Aborting.")
        return
    
    logger.info("Moving Robot to SAFE HOME...")
    bot.move_j(HOME_JOINTS, speed=0.5)
    while bot.is_moving(): time.sleep(0.1)

    logger.info("System Ready. Monitoring Printer...")

    while True:
        try:
            # 2. MONITORING
            status = printer.get_status()
            if status != "complete":
                 time.sleep(5)
                 continue
            
            logger.info("✅ Print Complete detected!")

            # 3. COOLDOWN
            while True:
                temp = printer.get_bed_temperature()
                logger.info(f"Waiting for Bed Cooldown... Current: {temp:.1f}°C / Target: {BED_COOLDOWN_TARGET}°C")
                if temp <= BED_COOLDOWN_TARGET:
                    logger.info("❄️ Bed is cool. Proceeding to harvest.")
                    break
                time.sleep(5) 

            # 4. HARVEST SEQUENCE
            logger.info("--- STARTING HARVEST SEQUENCE ---")

            # A. Open Gripper (Pre-emptive)
            bot.gripper_open()
            time.sleep(1.0)

            # B. Approach
            logger.info("Moving to Pre-Grasp...")
            bot.move_j(PRE_GRASP_JOINTS)
            while bot.is_moving(): time.sleep(0.1)

            # C. Enter (Linear)
            logger.info("Moving to Grasp (Linear)...")
            bot.move_l(GRASP_POSE_L, speed=0.1)
            while bot.is_moving(): time.sleep(0.1)

            # --- MANUAL CHECKPOINT ---
            print("\n" + "!"*60)
            input("👉 CHECKPOINT: Position Good? Press ENTER to GRIP...")
            print("!"*60 + "\n")

            # D. Grab
            logger.info("Closing Gripper...")
            bot.gripper_close()
            time.sleep(1.5) # Wait for grip

            # E. Detach (Lift)
            LIFT_POSE = list(GRASP_POSE_L)
            LIFT_POSE[2] += 0.05 # Lift Z+ 50mm
            
            logger.info("Lifting Part...")
            bot.move_l(LIFT_POSE, speed=0.05) 
            time.sleep(0.5)
            while bot.is_moving(): time.sleep(0.1)

            # F. SAFETY EXIT (Maneuver out of enclosure)
            logger.info("Executing Safety Maneuver (Exiting Cage)...")
            bot.move_j(EXIT_JOINTS, speed=0.6)
            while bot.is_moving(): time.sleep(0.1)

            # G. Deposit
            logger.info("Moving to Drop Zone...")
            bot.move_j(DROP_JOINTS, speed=1.0)
            time.sleep(0.5)
            while bot.is_moving(): time.sleep(0.1)

            logger.info("Dropping Part...")
            bot.gripper_open()
            time.sleep(1.5)

            # H. Return Home
            logger.info("Harvest Complete. Returning Home...")
            bot.move_j(HOME_JOINTS, speed=0.8)
            time.sleep(1.0)
            while bot.is_moving(): time.sleep(0.1)

            # 5. RESET PRINTER
            logger.info("Clearing Printer Status...")
            printer.execute_gcode("M84") 
            time.sleep(5)
            
            # --- FINISH PROGRAM ---
            logger.info("Pick and place complete.")
            bot.disconnect()
            break 

        except KeyboardInterrupt:
            logger.info("Stopping RoboFab Orchestrator...")
            bot.stop()
            bot.disconnect()
            break
        except Exception as e:
            logger.error(f"Unexpected Error: {e}")
            bot.stop()
            time.sleep(5)

if __name__ == "__main__":
    main()
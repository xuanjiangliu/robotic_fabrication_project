import time
import logging
import sys
import os
import requests

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# REAL DRIVERS ONLY
from pkg.drivers.ur_rtde_wrapper import URRobot
from pkg.drivers.sv08_moonraker import MoonrakerClient

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"
PRINTER_IP = "192.168.50.231"
API_URL = "http://127.0.0.1:5000/api"

# --- WAYPOINTS ---
HOME_JOINTS = [-1.49171, -2.06804, -1.98381, -2.23716, -1.48927, -3.16102]
PRE_GRASP_JOINTS = [-1.48798, -2.28912, -1.55682, -2.58710, -1.55443, -3.16062]
GRASP_POSE_L = [-0.05414, -0.89501, 0.01759, -0.01788, 2.56380, -1.73551]
EXIT_JOINTS = [-1.47797, -2.05317, -1.92593, -2.38268, -1.49959, -3.08864]
DROP_JOINTS = [-2.02408, -2.05317, -1.93757, -3.03030, -1.17494, -2.56292]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [Orchestrator] - %(message)s')
logger = logging.getLogger()

def run_harvest_sequence(bot, speed_factor=1.0):
    """
    Executes harvest. 
    Applies 'speed_factor' (0.1 to 1.0) to all moves for safety override.
    """
    logger.info(f"--- STARTING HARVEST (Speed: {speed_factor*100:.0f}%) ---")

    def safe_speed(nominal_speed):
        return nominal_speed * speed_factor

    # A. Approach
    bot.gripper_open()
    bot.move_j(PRE_GRASP_JOINTS, speed=safe_speed(0.8))
    bot.move_l(GRASP_POSE_L, speed=safe_speed(0.1))
    
    # B. Grab
    logger.info("Gripping...")
    bot.gripper_close()
    time.sleep(1.5)

    # C. Detach
    LIFT_POSE = list(GRASP_POSE_L)
    LIFT_POSE[2] += 0.05 
    bot.move_l(LIFT_POSE, speed=safe_speed(0.05))
    
    # D. Exit & Drop
    bot.move_j(EXIT_JOINTS, speed=safe_speed(0.6))
    bot.move_j(DROP_JOINTS, speed=safe_speed(1.0))
    bot.gripper_open()
    time.sleep(1.5)

    # E. Reset
    bot.move_j(HOME_JOINTS, speed=safe_speed(0.8))
    logger.info("Harvest Complete.")

def report_status(robot_state, printer_state, temp=0.0, progress=0.0, console=[]):
    """Helper to push telemetry to Dashboard."""
    try:
        requests.post(f"{API_URL}/status/update", json={
            "robot": robot_state,
            "printer": printer_state,
            "temp": temp,
            "progress": progress,
            "console": console
        }, timeout=1)
    except:
        pass # Don't crash if Dashboard is reloading

def main():
    logger.info("Initializing Active Orchestrator (Hardware Mode)...")
    logger.info(f"Targeting Robot: {ROBOT_IP} | Printer: {PRINTER_IP}")

    bot = URRobot(ROBOT_IP)
    printer = MoonrakerClient(PRINTER_IP)

    if not bot.connect():
        logger.error("Robot Connection Failed.")
        return

    # Home Robot
    bot.move_j(HOME_JOINTS, speed=0.5) # type: ignore

    while True:
        try:
            # 1. IDLE LOOP & TELEMETRY
            p_status = printer.get_status()
            p_temp = printer.get_bed_temperature()
            
            # Fetch Console Logs (Safely Check if method exists on Real Driver)
            p_console = []
            if hasattr(printer, 'get_console_lines'):
                p_console = printer.get_console_lines(limit=8)
            
            report_status("Idle", p_status, p_temp, 0.0, p_console)

            # 2. POLL FOR WORK
            try:
                resp = requests.get(f"{API_URL}/jobs/next", timeout=2)
            except requests.exceptions.ConnectionError:
                logger.warning("Waiting for Dashboard API...")
                time.sleep(5)
                continue
            
            if resp.status_code == 204:
                # No work
                time.sleep(2)
                continue
            
            # 3. JOB RECEIVED
            payload = resp.json()
            job = payload['job']
            settings = payload['settings']
            
            logger.info(f"📥 Received Job: {job['id']}")
            logger.info(f"⚙️ Applying Settings: Temp={settings['bed_temp']}C, Speed={settings['speed']}")

            # 4. UPLOAD & PRINT
            report_status("Working", "Uploading", p_temp, 0.0, p_console)
            
            filename = f"job_{job['id']}.gcode"
            if not printer.upload_gcode(job['gcode'], filename):
                logger.error("Upload failed.")
                continue 
            
            if not printer.start_print(filename):
                logger.error("Print start failed.")
                continue

            # 5. MONITOR PRINT
            while True:
                p_status = printer.get_status()
                p_temp = printer.get_bed_temperature()
                p_prog = printer.get_progress()
                if hasattr(printer, 'get_console_lines'):
                    p_console = printer.get_console_lines(limit=8)
                
                report_status("Waiting (Print)", p_status, p_temp, p_prog, p_console)
                
                if p_status == "complete":
                    break
                elif p_status in ["error", "offline"]:
                    logger.error("Printer Error.")
                    break
                time.sleep(2) 

            if p_status != "complete":
                continue 

            # 6. COOLDOWN
            target_temp = settings['bed_temp']
            logger.info(f"Cooling down to {target_temp:.1f}C...")
            
            while True:
                curr_temp = printer.get_bed_temperature()
                report_status("Waiting (Cool)", "Cooling", curr_temp, 1.0, p_console)
                
                if curr_temp <= target_temp:
                    break
                time.sleep(5)

            # 7. HARVEST
            if settings['auto_harvest']:
                report_status("Harvesting", "Complete", curr_temp, 1.0, p_console)
                run_harvest_sequence(bot, speed_factor=settings['speed'])
            else:
                logger.info("⚠️ Auto-Harvest Disabled.")

            # 8. REPORT COMPLETE
            requests.post(f"{API_URL}/jobs/{job['id']}/complete", json={"result": "success"})
            
            # 9. CLEANUP
            printer.execute_gcode("M84") 

        except KeyboardInterrupt:
            logger.info("Stopping...")
            bot.stop()
            bot.disconnect()
            break
        except Exception as e:
            logger.error(f"Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
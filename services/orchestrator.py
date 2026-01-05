import time
import logging
import sys
import os
import requests
import yaml  # <--- New Dependency: pip install pyyaml

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pkg.drivers.robotiq_v2 import RTDETriggerClient
from pkg.drivers.sv08_moonraker import MoonrakerClient

# --- CONFIGURATION LOADING ---
# Path to the shared configuration file
CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../config/cell_config.yaml'))

def load_network_config(path):
    """
    Loads network settings from the YAML config file.
    """
    if not os.path.exists(path):
        print(f"❌ CRITICAL ERROR: Configuration file not found at: {path}")
        sys.exit(1)
        
    try:
        with open(path, 'r') as f:
            full_config = yaml.safe_load(f)
            return full_config.get('network', {})
    except Exception as e:
        print(f"❌ CRITICAL ERROR: Failed to parse config file. {e}")
        sys.exit(1)

# Load Configuration
net_config = load_network_config(CONFIG_PATH)

# Apply Configuration
ROBOT_IP = net_config.get('robot_ip')
PRINTER_IP = net_config.get('printer_ip')
CONTROL_PC_IP = net_config.get('control_pc_ip', '127.0.0.1')
API_URL = f"http://{CONTROL_PC_IP}:5000/api"

# Tuning: How long to wait for the robot to finish the physical harvest?
HARVEST_DURATION_SEC = 10

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [Orchestrator] - %(message)s')
logger = logging.getLogger()

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
    logger.info("Initializing Orchestrator (Standard Mode)...")
    logger.info(f"Loaded Config -> Robot: {ROBOT_IP} | Printer: {PRINTER_IP} | Dashboard: {CONTROL_PC_IP}")

    # 1. Initialize Clients
    if not ROBOT_IP or not PRINTER_IP:
        logger.error("❌ Configuration Error: Missing IP addresses in cell_config.yaml")
        return

    trigger = RTDETriggerClient(ROBOT_IP)
    printer = MoonrakerClient(PRINTER_IP)

    # 2. Establish Connection to Robot's Nervous System
    if not trigger.connect():
        logger.error(f"❌ Robot Trigger Connection Failed to {ROBOT_IP}. Check Network.")
        return
    
    # 3. Safety Check: Is the Tablet Program actually running?
    if not trigger.is_program_running():
        logger.warning("⚠️  Robot Program is NOT running.")
        logger.warning("    Action: Go to Tablet -> Load Program -> Press Play.")

    while True:
        try:
            # --- PHASE 1: IDLE MONITORING ---
            p_status = printer.get_status()
            p_temp = printer.get_bed_temperature()
            
            # Fetch Console Logs
            p_console = []
            if hasattr(printer, 'get_console_lines'):
                p_console = printer.get_console_lines(limit=8)
            
            # Check Robot Health
            r_status = "Ready" if trigger.is_program_running() else "Halted"
            
            report_status(r_status, p_status, p_temp, 0.0, p_console)

            # --- PHASE 2: POLL FOR WORK ---
            try:
                resp = requests.get(f"{API_URL}/jobs/next", timeout=2)
            except requests.exceptions.ConnectionError:
                logger.warning(f"Waiting for Dashboard API at {CONTROL_PC_IP}...")
                time.sleep(5)
                continue
            
            if resp.status_code == 204:
                # No work in queue
                time.sleep(2)
                continue
            
            # --- PHASE 3: JOB STARTED ---
            payload = resp.json()
            job = payload['job']
            settings = payload['settings']
            
            logger.info(f"📥 Received Job: {job['id']}")
            logger.info(f"⚙️ Settings: Temp={settings['bed_temp']}C, Auto-Harvest={settings['auto_harvest']}")

            # --- Auto-Home Before Print ---
            logger.info("🏠 Homing Printer (G28)...")
            printer.execute_gcode("G28")
            # Wait briefly to ensure Klipper registers the command and starts moving
            # before we attempt to start the print file.
            time.sleep(15) 
            # -----------------------------------

            # Upload & Start Print
            report_status(r_status, "Uploading", p_temp, 0.0, p_console)
            filename = f"job_{job['id']}.gcode"
            
            if not printer.upload_gcode(job['gcode'], filename):
                logger.error("Upload failed.")
                continue 
            
            if not printer.start_print(filename):
                logger.error("Print start failed.")
                continue

            # --- PHASE 4: PRINTING LOOP ---
            while True:
                p_status = printer.get_status()
                p_temp = printer.get_bed_temperature()
                p_prog = printer.get_progress()
                if hasattr(printer, 'get_console_lines'):
                    p_console = printer.get_console_lines(limit=8)
                
                report_status(r_status, p_status, p_temp, p_prog, p_console)
                
                if p_status == "complete":
                    break
                elif p_status in ["error", "offline"]:
                    logger.error("Printer Error.")
                    break
                time.sleep(2) 

            if p_status != "complete":
                continue 

            # --- PHASE 5: COOLDOWN ---
            target_temp = settings['bed_temp']
            logger.info(f"Cooling down to {target_temp:.1f}C...")
            
            while True:
                curr_temp = printer.get_bed_temperature()
                report_status(r_status, "Cooling", curr_temp, 1.0, p_console)
                
                if curr_temp <= target_temp:
                    break
                time.sleep(5)

            # --- PHASE 6: THE HANDSHAKE (HARVEST) ---
            if settings['auto_harvest']:
                logger.info("🤖 Initiating Harvest Sequence...")
                report_status("Harvesting", "Complete", curr_temp, 1.0, p_console)
                
                # A. Verify Link
                if trigger.is_program_running():
                    # B. Pull the Trigger
                    if trigger.trigger_cycle():
                        logger.info("✅ Signal Sent (Reg 18 -> 1).")
                        logger.info(f"⏳ Waiting {HARVEST_DURATION_SEC}s for robot execution...")
                        
                        # C. Wait for Physical Action (Original Logic)
                        time.sleep(HARVEST_DURATION_SEC)
                        
                        logger.info("✅ Harvest Time Elapsed.")
                    else:
                        logger.error("❌ Failed to send trigger signal.")
                else:
                    logger.error("❌ Robot is NOT running. Cannot Harvest.")
            else:
                logger.info("⚠️ Auto-Harvest Disabled by Job Settings.")

            # --- PHASE 7: FINISH ---
            requests.post(f"{API_URL}/jobs/{job['id']}/complete", json={"result": "success"})
            
            # Cleanup Printer Motors
            printer.execute_gcode("M84") 

        except KeyboardInterrupt:
            logger.info("Stopping Orchestrator...")
            trigger.disconnect()
            break
        except Exception as e:
            logger.error(f"Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
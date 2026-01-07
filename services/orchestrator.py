import time
import logging
import sys
import os
import requests
import yaml

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pkg.drivers.robotiq_v2 import RTDETriggerClient
from pkg.drivers.sv08_moonraker import MoonrakerClient
from pkg.core.characterization_manager import CharacterizationManager, CharacterizationJob

# --- CONFIGURATION LOADING ---
CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../config/cell_config.yaml'))

def load_network_config(path):
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
ROBOT_IP = net_config.get('robot_ip')
PRINTER_IP = net_config.get('printer_ip')
CONTROL_PC_IP = net_config.get('control_pc_ip', '127.0.0.1')
API_URL = f"http://{CONTROL_PC_IP}:5000/api"

# Tuning
HARVEST_DURATION_SEC = 33

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [Orchestrator] - %(message)s')
logger = logging.getLogger()

def report_status(robot_state, printer_state, temp=0.0, progress=0.0, console=[]):
    try:
        requests.post(f"{API_URL}/status/update", json={
            "robot": robot_state,
            "printer": printer_state,
            "temp": temp,
            "progress": progress,
            "console": console
        }, timeout=1)
    except:
        pass 

def main():
    logger.info("Initializing Orchestrator (Robust Connection)...")
    logger.info(f"Loaded Config -> Robot: {ROBOT_IP} | Printer: {PRINTER_IP}")

    if not ROBOT_IP or not PRINTER_IP:
        logger.error("❌ Configuration Error: Missing IP addresses.")
        return

    trigger = RTDETriggerClient(ROBOT_IP)
    printer = MoonrakerClient(PRINTER_IP)

    char_manager = CharacterizationManager(camera_idx=1, pneu_port="COM5")

    # Initial Connection
    if not trigger.connect():
        logger.error(f"❌ Robot Trigger Connection Failed to {ROBOT_IP}.")
    
    # Safety Check (Wrapped)
    try:
        if not trigger.is_program_running():
            logger.warning("⚠️  Robot Program is NOT running (or not connected).")
    except Exception:
        pass # Ignore startup error, loop will fix it

    while True:
        try:
            # --- PHASE 1: IDLE MONITORING ---
            p_status = printer.get_status()
            p_temp = printer.get_bed_temperature()
            
            p_console = []
            if hasattr(printer, 'get_console_lines'):
                p_console = printer.get_console_lines(limit=8)
            
            # --- FIXED: ROBUST ROBOT CHECK ---
            # If the robot kicked us off (Boost Exception), this block catches it 
            # and automatically reconnects.
            try:
                if trigger.is_program_running():
                    r_status = "Ready"
                else:
                    r_status = "Halted"
            except Exception as e:
                # 1. Catch the crash
                logger.warning(f"⚠️ Robot Disconnected ({e}). Reconnecting...")
                # 2. Reset the interface
                trigger.disconnect()
                # 3. Try to reconnect immediately
                if trigger.connect():
                    # Check again
                    try:
                        r_status = "Ready" if trigger.is_program_running() else "Halted"
                    except:
                        r_status = "Offline"
                else:
                    r_status = "Offline"
            # ---------------------------------
            
            report_status(r_status, p_status, p_temp, 0.0, p_console)

            # --- PHASE 2: POLL FOR WORK ---
            try:
                resp = requests.get(f"{API_URL}/jobs/next", timeout=2)
            except requests.exceptions.ConnectionError:
                time.sleep(5)
                continue
            
            if resp.status_code == 204:
                time.sleep(2)
                continue
            
            # --- PHASE 3: JOB STARTED ---
            payload = resp.json()
            job = payload['job']
            settings = payload['settings']
            
            logger.info(f"📥 Received Job: {job['id']}")

            # Auto-Home
            logger.info("🏠 Homing Printer (G28)...")
            printer.execute_gcode("G28")
            time.sleep(15) 

            # Upload & Start
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
                
                # We also check robot status here to keep the dashboard alive
                # But we don't spam the logs if it's offline during printing
                try:
                    r_status = "Ready" if trigger.is_program_running() else "Halted"
                except:
                    r_status = "Offline"

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

            # OPTIMIZATION: Pre-warm camera while waiting for temperature
            # char_manager.engine.setup()
            
            while True:
                curr_temp = printer.get_bed_temperature()
                report_status(r_status, "Cooling", curr_temp, 1.0, p_console)
                if curr_temp <= target_temp:
                    break
                time.sleep(5)

            # --- PHASE 6: THE DOUBLE-HANDSHAKE (HARVEST & TEST) ---
            if settings['auto_harvest']:
                logger.info("🤖 Initiating Synchronized Harvest & Characterization...")
                
                try:
                    # 1. Force a check/reconnect if needed
                    try:
                        trigger.is_program_running()
                    except:
                        logger.warning("⚠️ Robot offline before harvest. Reconnecting...")
                        trigger.disconnect()
                        trigger.connect()

                    # 2. Proceed with Harvest
                    if trigger.is_program_running():
                        # --- HANDSHAKE 1: START HARVEST ---
                        if trigger.trigger_cycle():
                            logger.info("✅ Signal 1 Sent (Reg 18 -> 1). Robot starting harvest...")
                            
                            # 3. Wait for robot to reach the station (Travel Time)
                            # logger.info(f"⏳ Waiting {HARVEST_DURATION_SEC}s for arrival...")
                            # time.sleep(HARVEST_DURATION_SEC)
                            
                            # --- CHARACTERIZATION PHASE ---
                            logger.info("🔬 Robot at station. Starting vision analysis...")
                            report_status("Characterizing", "Stationary", curr_temp, 1.0, p_console)
                            
                            char_job = CharacterizationJob(
                                job_id=str(job['id']),
                                channel=4,  # Standard channel for PneuNet
                                pulse_duration_ms=2000,
                                actuator_type="FGF_Actuator"
                            )

                            # This blocks until the 3-state loop (Baseline -> Inflation -> Recoil) finishes
                            test_success = char_manager.run_autonomous_test(char_job)
                            
                            if test_success:
                                logger.info("✅ Characterization complete.")
                            else:
                                logger.error("❌ Characterization test failed. Releasing robot for safety.")

                            # --- HANDSHAKE 2: RELEASE ---
                            # Pulse Reg 18 again to tell the pendant to exit the SECOND wait node
                            logger.info("🔓 Releasing Robot to complete sequence...")
                            trigger.trigger_cycle()
                            logger.info("✅ Signal 2 Sent (Reg 18 -> 1). Harvest cycle complete.")
                        else:
                            logger.error("❌ Failed to send trigger signal.")
                    else:
                        logger.error("❌ Robot is NOT running/connected. Cannot Harvest.")

                except Exception as e:
                    logger.error(f"❌ Critical Harvest/Char Failure: {e}")

            # --- PHASE 7: FINISH ---
            requests.post(f"{API_URL}/jobs/{job['id']}/complete", json={"result": "success"})
            char_manager.engine.cam.stop() # Release camera for next job
            printer.execute_gcode("M84") 
            printer.execute_gcode("SDCARD_RESET_FILE") 

        except KeyboardInterrupt:
            logger.info("Stopping Orchestrator...")
            trigger.disconnect()
            break
        except Exception as e:
            logger.error(f"Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
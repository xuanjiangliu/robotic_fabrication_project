import requests
import time
import logging

class MoonrakerClient:
    def __init__(self, ip_address, port=7125):
        self.base_url = f"http://{ip_address}:{port}"
        self.logger = logging.getLogger("MoonrakerClient")

    def get_status(self):
        """
        Queries Klipper for the current print status.
        Returns: 'standby', 'printing', 'paused', 'complete', 'error'
        """
        url = f"{self.base_url}/printer/objects/query?print_stats"
        try:
            response = requests.get(url, timeout=2)
            response.raise_for_status()
            data = response.json()
            state = data['result']['status']['print_stats']['state']
            return state
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return "offline"

    def get_progress(self):
        """Returns the print progress as a percentage (0.0 to 1.0)."""
        url = f"{self.base_url}/printer/objects/query?display_status"
        try:
            response = requests.get(url, timeout=2)
            data = response.json()
            progress = data['result']['status']['display_status']['progress']
            return progress
        except Exception:
            return 0.0

    def get_bed_temperature(self):
        """Returns the current bed temperature in Celsius."""
        url = f"{self.base_url}/printer/objects/query?heater_bed"
        try:
            response = requests.get(url, timeout=2)
            data = response.json()
            temp = data['result']['status']['heater_bed']['temperature']
            return float(temp)
        except Exception:
            return 999.0 

    def get_console_lines(self, limit=10):
        """Fetches the last N lines from the Klipper G-Code console."""
        url = f"{self.base_url}/server/gcode_store"
        try:
            response = requests.get(url, timeout=2)
            data = response.json()
            logs = data['result']['gcode_store']
            messages = [entry['message'] for entry in logs]
            return messages[-limit:]
        except Exception:
            return []

    def upload_gcode(self, gcode_content, filename="job.gcode"):
        """Uploads G-code string to the printer."""
        url = f"{self.base_url}/server/files/upload"
        files = {'file': (filename, gcode_content, 'application/octet-stream')}
        data = {'root': 'gcodes'} 
        
        try:
            response = requests.post(url, files=files, data=data, timeout=10) # Increased to 10s
            response.raise_for_status()
            self.logger.info(f"Uploaded {filename}")
            return True
        except Exception as e:
            self.logger.error(f"Upload failed: {e}")
            return False

    def start_print(self, filename="job.gcode"):
        """Starts printing the specified file."""
        url = f"{self.base_url}/printer/print/start"
        payload = {'filename': filename}
        try:
            # FIX: Increased timeout from 2s to 10s
            requests.post(url, json=payload, timeout=10)
            self.logger.info(f"Started print: {filename}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start print: {e}")
            return False

    def execute_gcode(self, gcode_command):
        """Sends a raw G-code command."""
        url = f"{self.base_url}/printer/gcode/script"
        payload = {'script': gcode_command}
        try:
            requests.post(url, json=payload, timeout=2)
            return True
        except Exception:
            return False
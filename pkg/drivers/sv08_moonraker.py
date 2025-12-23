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
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Connection failed: {e}")
            return "error"

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

    def execute_gcode(self, gcode_command):
        """Sends a G-code command (or macro) to the printer."""
        url = f"{self.base_url}/printer/gcode/script"
        payload = {'script': gcode_command}
        try:
            requests.post(url, json=payload, timeout=2)
            self.logger.info(f"Sent G-Code: {gcode_command}")
            return True
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send G-Code: {e}")
            return False
        
    def get_bed_temperature(self):
        """Returns the current bed temperature in Celsius."""
        # Klipper Object Model query
        url = f"{self.base_url}/printer/objects/query?heater_bed"
        try:
            response = requests.get(url, timeout=2)
            data = response.json()
            # Navigate the JSON structure: result -> status -> heater_bed -> temperature
            temp = data['result']['status']['heater_bed']['temperature']
            return float(temp)
        except Exception as e:
            self.logger.error(f"Failed to read Temp: {e}")
            return 999.0 # Return high value to prevent unsafe harvesting on error

# Quick test if run directly
if __name__ == "__main__":
    # Uses your IP from context
    client = MoonrakerClient("192.168.50.231") 
    print(f"Printer State: {client.get_status()}")
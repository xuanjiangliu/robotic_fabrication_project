# pkg/drivers/pneumatic_serial.py
import time
import logging

class MockPneumaticSerial:
    """
    Simulates the Arduino Uno pneumatic controller asynchronously.
    Allows the main loop to continue processing vision frames while a pulse is active.
    """
    def __init__(self, port='/dev/ttyFake', baud=115200):
        self.is_connected = True
        self._active_pulse = None # Stores (end_time, channel)
        logging.info(f"Initialized Non-Blocking Mock Pneumatic Serial on {port}")

    def start_pulse(self, channel: int, duration_ms: int):
        """
        Starts a timed pulse on a specific channel without blocking.
        """
        if not (1 <= channel <= 4):
            raise ValueError("Channel must be between 1 and 4")
        
        if self.is_busy():
            logging.warning("⚠️ Pulse already in progress. Ignoring new command.")
            return False

        # Calculate when this pulse should end
        end_time = time.time() + (duration_ms / 1000.0)
        self._active_pulse = {
            "channel": channel,
            "end_time": end_time
        }

        logging.info(f"[Mock Serial] Outbound: START:{channel}:{duration_ms}")
        logging.info(f"[Mock Serial] Inbound: STATUS:BUSY:CH{channel}")
        return True

    def is_busy(self):
        """
        Checks if a pulse is currently active. Automatically transitions to IDLE when time expires.
        """
        if self._active_pulse is None:
            return False

        if time.time() >= self._active_pulse["end_time"]:
            ch = self._active_pulse["channel"]
            logging.info(f"[Mock Serial] Inbound: STATUS:DONE:CH{ch}")
            self._active_pulse = None
            return False

        return True

    def abort(self):
        """Immediate safety cutoff."""
        if self._active_pulse:
            logging.warning("🛑 Pulse Aborted. Closing all valves.")
            self._active_pulse = None

    def close(self):
        self.abort()
        logging.info("Mock Serial connection closed.")
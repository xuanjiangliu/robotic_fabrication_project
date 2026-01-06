import serial
import time
import logging

class PneumaticSerial:
    """
    Driver for the Arduino Uno PneuNet Controller.
    Handles timed inflation pulses over Serial without blocking the main thread.
    """
    def __init__(self, port="COM5", baud=115200, timeout=0.1):
        self.port = port
        self.baud = baud
        self.ser = None
        self._busy = False
        self._active_channel = None
        self.logger = logging.getLogger("RoboFab.Pneumatics")

        try:
            # Establishing the Physical/Link Layer connection
            self.ser = serial.Serial(self.port, self.baud, timeout=timeout)
            # Arduino resets on connection; wait 2s for bootloader to finish
            time.sleep(2.0) 
            self.logger.info(f"✅ Connected to Arduino on {self.port}")
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to Serial: {e}")
            self.ser = None # Explicitly set to None on failure

    def start_pulse(self, channel: int, duration_ms: int):
        """
        Sends the pulse command string to Arduino in the format START:CH:TIME\n.
        """
        if not self.ser or not self.ser.is_open:
            self.logger.error("Serial port not open. Cannot start pulse.")
            return False

        if self._busy:
            self.logger.warning("⚠️ Pulse already in progress. Command ignored.")
            return False

        if not (1 <= channel <= 4):
            self.logger.error(f"Invalid channel requested: {channel}")
            return False

        command = f"START:{channel}:{duration_ms}\n"
        self.ser.write(command.encode('utf-8'))
        self._busy = True
        self._active_channel = channel
        self.logger.info(f"Outbound: {command.strip()}")
        return True

    def is_busy(self):
        """
        Polls the serial buffer for the 'STATUS:DONE' handshake signal.
        """
        if not self._busy:
            return False

        # FIX: Explicit check to prevent "in_waiting is not an attribute of None"
        if self.ser is None or not self.ser.is_open:
            self.logger.error("Serial connection lost during active pulse.")
            self._busy = False
            return False

        # Check for data in the buffer
        if self.ser.in_waiting > 0:
            line = self.ser.readline().decode('utf-8').strip()
            
            # Match the protocol: STATUS:DONE:CH<num>
            expected = f"STATUS:DONE:CH{self._active_channel}"
            if expected in line:
                self.logger.info(f"Inbound Handshake: {line}")
                self._busy = False
                self._active_channel = None
                return False
            elif "ERROR" in line:
                self.logger.error(f"Arduino Logic Error: {line}")
                self._busy = False
                return False

        return True

    def abort(self):
        """Immediate safety cutoff sent to Arduino to close all valves."""
        if self.ser and self.ser.is_open:
            self.ser.write(b"ABORT\n")
            self._busy = False
            self.logger.warning("🛑 Pulse Aborted. All valves closing.")

    def close(self):
        """Standard cleanup for the serial interface."""
        self.abort()
        if self.ser:
            self.ser.close()
            self.logger.info("Pneumatic Serial connection closed.")
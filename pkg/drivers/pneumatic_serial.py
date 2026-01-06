import time
import logging


# a simulated PneumaticSerial driver that mimics the Arduino's behavior
class MockPneumaticSerial:
    """
    Simulates the Arduino Uno pneumatic controller for development.
    Adheres to the START:CH:TIME protocol.
    """
    def __init__(self, port='/dev/ttyFake', baud=115200):
        self.is_connected = True
        logging.info(f"Initialized Mock Pneumatic Serial on {port}")

    def send_pulse(self, channel: int, duration_ms: int):
        if not (1 <= channel <= 4):
            raise ValueError("Channel must be between 1 and 4")
        
        logging.info(f"[Mock Serial] Outbound: START:{channel}:{duration_ms}")
        # Simulate the 'BUSY' status
        logging.info(f"[Mock Serial] Inbound: STATUS:BUSY:CH{channel}")
        
        # Simulate physical time passing
        time.sleep(duration_ms / 1000.0)
        
        # Simulate the 'DONE' status
        logging.info(f"[Mock Serial] Inbound: STATUS:DONE:CH{channel}")
        return True

    def close(self):
        logging.info("Mock Serial connection closed.")
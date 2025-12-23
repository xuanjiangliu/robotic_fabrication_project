"""
Robotiq Hand-E Driver (Modbus RTU Mode)
---------------------------------------------------------
HARDWARE SETTINGS (Tablet):
- Modbus Device Frequency: 10 Hz
- Slave ID: 1
- Sequential Mode: ON
- Signals: Grip_CMD (0), Grip_POS (1), Grip_FOR (2)
---------------------------------------------------------
"""

def get_activation_script():
    """
    Activates gripper.
    """
    return """
def rq_activate():
    # Diagnostic
    popup("RoboFab: Activating (10Hz Mode)...", "Status", False, False, blocking=False)
    
    # 1. Reset (Write 0 to Grip_CMD)
    modbus_set_output_register("Grip_CMD", 0)
    sleep(0.2)
    
    # 2. Set Force/Speed (Write to Grip_FOR)
    # 255 Speed, 150 Force -> 65430
    modbus_set_output_register("Grip_FOR", 65430)
    sleep(0.2)

    # 3. Activate (Write 256 to Grip_CMD)
    modbus_set_output_register("Grip_CMD", 256)
    
    sleep(2.0)
    popup("RoboFab: Gripper Active!", "Success", False, False, blocking=False)
end
rq_activate()
"""

def get_move_script(position_0_255):
    """
    Moves gripper.
    Waits 0.2s between setting Position and triggering Action
    to align with the 10Hz Modbus cycle.
    """
    pos = max(0, min(255, int(position_0_255)))
    
    # 2304 = 0x0900 (Activate + GoTo)
    return f"""
def rq_move():
    # 1. Set Position (Address 1)
    modbus_set_output_register("Grip_POS", {pos})
    
    # SAFETY PAUSE: 0.2s ensures we catch the next 10Hz cycle
    sleep(0.2)
    
    # 2. Set Action (Address 0)
    modbus_set_output_register("Grip_CMD", 2304)
end
rq_move()
"""
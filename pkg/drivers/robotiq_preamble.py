"""
Robotiq Hand-E Driver (Direct Hardware Connection - Slave ID 9)
---------------------------------------------------------
Target: Physical Modbus RTU Registers (1000, 1001, 1002)
Hardware Default Slave ID: 9
---------------------------------------------------------
"""

def get_activation_script():
    """
    Activates the gripper using Physical Register 1000.
    """
    return """
def rq_activate_direct():
    # 1. Reset (Write 0 to Register 1000)
    modbus_set_output_register("Grip_CMD", 0)
    sleep(0.5)
    
    # 2. Set Force & Speed (Register 1002)
    # Byte 4 (Speed 255) + Byte 5 (Force 150) -> 0xFF96 = 65430
    modbus_set_output_register("Grip_FOR", 65430)
    sleep(0.1)

    # 3. Activate (Register 1000)
    # Byte 0 (Action Request) = 1 (Activate) -> 256 (0x0100)
    modbus_set_output_register("Grip_CMD", 256)
    
    # Wait for activation movement
    sleep(2.0)
end
rq_activate_direct()
"""

def get_move_script(position_0_255):
    """
    Moves gripper using Physical Registers 1001 (Pos) and 1000 (Cmd).
    """
    pos = max(0, min(255, int(position_0_255)))
    
    return f"""
def rq_move_direct():
    # 1. Set Target Position (Register 1001)
    # Byte 3 is Position. Value 0-255 directly sets the lower byte.
    modbus_set_output_register("Grip_POS", {pos})
    
    # SAFETY PAUSE (10Hz bus limit)
    sleep(0.1)
    
    # 2. Trigger Action (Register 1000)
    # Activate (0x01) + GoTo (0x08) -> 0x09
    # Shifted to Byte 0 position -> 2304 (0x0900)
    modbus_set_output_register("Grip_CMD", 2304)
end
rq_move_direct()
"""
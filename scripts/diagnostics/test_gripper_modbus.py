import sys
import os
import time

# 1. Setup Import Paths (Matches your project structure)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pkg.drivers.ur_rtde_wrapper import URRobot

ROBOT_IP = "192.168.50.82"

def show_gate_popup(bot, message):
    """
    Acts as a 'Gate': 
    1. Sends a popup to the Tablet (Non-blocking).
    2. Pauses Python execution until you press ENTER.
    """
    print(f"\n🛑 [GATE] {message}")
    
    # URScript popup: popup(msg, title, warning, error, blocking)
    # We use blocking=False so it doesn't freeze the robot controller, 
    # but we pause Python to create the "Gate" effect.
    safe_msg = message.replace('"', "'") # Escape quotes
    cmd = f'popup("{safe_msg}", "Step Verification", False, False, False)\n'
    bot._send_socket_command(cmd)
    
    # Wait for user to verify
    input("   >> Press ENTER in terminal to execute action...")

def test_gripper_with_gates():
    print(f"--- EvoFab Gripper Test (Modbus + Gates) ---")
    print(f"Target: {ROBOT_IP}")
    
    bot = URRobot(ROBOT_IP)
    
    # 1. Connect & Activate
    print("\n1. Connecting...")
    if not bot.connect():
        print("❌ Failed to connect.")
        return
    
    # 2. Gate: Test Close
    show_gate_popup(bot, "Gripper is active. Ready to CLOSE?")
    print("   Sending CLOSE command...")
    bot.gripper_close()
    
    print("   Waiting 3s for movement...")
    time.sleep(3.0)

    # 3. Gate: Test Open
    show_gate_popup(bot, "Gripper Closed. Ready to OPEN?")
    print("   Sending OPEN command...")
    bot.gripper_open()
    
    print("   Waiting 3s for movement...")
    time.sleep(3.0)

    # 4. Gate: Finish
    show_gate_popup(bot, "Test Complete. Disconnect?")
    bot.disconnect()
    print("\n✅ Verification Finished.")

if __name__ == "__main__":
    test_gripper_with_gates()
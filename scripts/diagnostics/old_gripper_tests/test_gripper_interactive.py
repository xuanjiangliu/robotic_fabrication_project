import sys
import os
import time

# 1. Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pkg.drivers.ur_rtde_wrapper import URRobot
from pkg.drivers import robotiq_v2

# --- CONFIGURATION ---
ROBOT_IP = "192.168.50.82"

def user_gate(bot, title, instruction):
    """
    1. Sends a Popup to the Tablet (Non-blocking).
    2. Pauses Python until you press ENTER.
    """
    print(f"\n🛑 [GATE] {title}")
    print(f"   ℹ️  {instruction}")
    
    # Send Popup to Tablet to notify operator at the robot
    # popup(msg, title, warning, error, blocking)
    if bot and bot.connected:
        safe_msg = f"{title}: {instruction}".replace('"', "'")
        cmd = f'popup("{safe_msg}", "Interactive Test", False, False, False)\n'
        bot._send_socket_command(cmd)
    
    # Block Python execution here
    input("   👉 Press ENTER in terminal to Execute...")
    print("   🚀 Executing...")

def run_interactive_test():
    print(f"--- EvoFab Interactive Gripper Test ---")
    print(f"Target: {ROBOT_IP}")
    print("Requirement: 'Grip_CMD' (Addr 2), 'Grip_POS' (Addr 3), 'Grip_FOR' (Addr 4)")
    
    bot = URRobot(ROBOT_IP)
    
    # --- STEP 1: CONNECTION ---
    # We don't have a 'bot' connection yet, so no tablet popup, just terminal gate.
    print("\n🛑 [GATE] Connection & Activation")
    print("   ℹ️  Robot will connect and Gripper will CLACK/RESET immediately.")
    input("   👉 Press ENTER to Connect...")
    
    if not bot.connect():
        print("❌ Failed to connect.")
        return
    print("✅ Connected & Activated.")

    # --- STEP 2: CLOSE TEST ---
    user_gate(bot, "Test 1: CLOSE", "Gripper will close completely (255).")
    bot.gripper_close()
    time.sleep(2.0)

    # --- STEP 3: HALF-OPEN TEST (Precision Check) ---
    # This proves we have analog control, not just binary open/close
    user_gate(bot, "Test 2: HALF OPEN", "Gripper will move to 50% (Position 128).")
    
    # Manually sending a custom position script
    script_half = robotiq_v2.get_move_script(128)
    bot._send_socket_command(script_half)
    time.sleep(2.0)

    # --- STEP 4: OPEN TEST ---
    user_gate(bot, "Test 3: OPEN", "Gripper will open completely (0).")
    bot.gripper_open()
    time.sleep(2.0)

    # --- STEP 5: FINISH ---
    user_gate(bot, "Test Complete", "Disconnecting from robot.")
    bot.disconnect()
    print("\n✅ Verification Finished.")

if __name__ == "__main__":
    run_interactive_test()
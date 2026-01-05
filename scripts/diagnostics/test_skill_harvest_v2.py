import sys
import os

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pkg.drivers.ur_rtde_wrapper import URRobot
from pkg.skills.visual_harvest import VisualHarvester

ROBOT_IP = "192.168.50.82"

def main():
    print("--- TESTING VISUAL HARVESTER V2 (STANDALONE) ---")
    
    # 1. Setup
    bot = URRobot(ROBOT_IP)
    if not bot.connect():
        print("❌ Cannot run test: Robot disconnected.")
        return
    
    # 2. Check Pose immediately to ensure data flow
    if bot.get_tcp_pose() is None:
        print("❌ Connected, but no pose data. Check Controller 'Remote Control' status.")
        bot.disconnect()
        return

    skill = VisualHarvester(bot)
    
    # 3. Loop
    while True:
        print("\n--------------------------------")
        print("Place a Benchy on the bed.")
        cmd = input("Press ENTER to Harvest, 'q' to Quit: ")
        if cmd == 'q': break
        
        try:
            success = skill.execute()
            if success:
                print("✅ Harvest Reported Success.")
            else:
                print("❌ Harvest Failed.")
        except Exception as e:
            print(f"❌ Critical Error during execution: {e}")

    bot.disconnect()

if __name__ == "__main__":
    main()
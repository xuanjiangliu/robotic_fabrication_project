import sys
import os
import time

# Setup Import Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pkg.drivers.ur_rtde_wrapper import URRobot
from pkg.skills.visual_harvest import VisualHarvester

# Configuration
ROBOT_IP = "192.168.50.82"

def main():
    print("--- Testing Visual Harvest Skill (Isolated) ---")
    
    # 1. Initialize Driver
    bot = URRobot(ROBOT_IP)
    if not bot.connect():
        print("❌ Failed to connect to robot.")
        return

    # 2. Initialize Skill
    try:
        harvester = VisualHarvester(bot)
        print("✅ VisualHarvester Initialized.")
    except Exception as e:
        print(f"❌ Failed to init harvester: {e}")
        bot.disconnect()
        return

    # 3. Execution
    print("\n⚠️ WARNING: Robot will MOVE immediately.")
    print("Ensure the bed is clear and a test object is present.")
    input("Press ENTER to start the sequence...")
    
    try:
        start_time = time.time()
        success = harvester.execute()
        duration = time.time() - start_time
        
        if success:
            print(f"\n✅ Harvest Sequence Complete in {duration:.1f}s")
        else:
            print(f"\n❌ Harvest Sequence FAILED (Object not found or lost)")
            
    except KeyboardInterrupt:
        print("\n🛑 Stopped by User")
        bot.stop()
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        bot.stop()
    
    # Cleanup
    bot.disconnect()

if __name__ == "__main__":
    main()
import socket
import time

ROBOT_IP = "192.168.50.82"
PORT = 30020  # Interpreter Mode (Better for debugging)

def interpreter_test():
    print(f"Connecting to {ROBOT_IP}:{PORT}...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((ROBOT_IP, PORT))
        
        # 1. READ RESPONSE (The robot sends a 'hello' message on connect)
        print("Waiting for welcome message...")
        data = s.recv(1024)
        print(f"Robot said: {data.decode('utf-8').strip()}")
        
        # 2. SEND COMMAND
        # We send a simple text print first to confirm execution
        cmd_1 = 'textmsg("Interpreter Test: ALIVE")\n'
        print(f"Sending: {cmd_1.strip()}")
        s.send(cmd_1.encode('utf-8'))
        
        # Read Reply
        reply = s.recv(1024)
        print(f"Reply 1: {reply.decode('utf-8').strip()}")
        
        # 3. SEND MOVE COMMAND
        # We use a very small relative move (0.1 rad is ~6 degrees)
        # We use 'speedj' or 'movej' depending on Interpreter support
        # Let's try a safe, hardcoded move relative to current? 
        # Actually, Interpreter mode handles single commands best.
        
        print("Sending Move Command...")
        # Note: Interpreter mode is strict. We will try a textmsg first.
        # If the log shows "Interpreter Test: ALIVE", we know execution works.
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        s.close()

if __name__ == "__main__":
    interpreter_test()
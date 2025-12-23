import socket

ROBOT_IP = "192.168.50.82"
PORT = 30002  # Secondary Client Interface (Executes raw URScript)

def show_popup():
    print(f"Connecting to {ROBOT_IP}:{PORT}...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((ROBOT_IP, PORT))
        
        # URScript command to show a popup on the tablet
        script = 'popup("Hello William! Control is Active.", "Test", warning=False, error=False, blocking=True)\n'
        
        print("Sending Popup Command...")
        s.send(script.encode('utf-8'))
        
        print("Command sent. CHECK THE TABLET NOW.")
        s.close()
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    show_popup()
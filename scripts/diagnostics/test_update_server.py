import socket

# Configuration
HOST = '0.0.0.0'  # Listen on all network interfaces
PORT = 50002      # Default port for External Control (Check your URCap settings!)

def run_server():
    print(f"--- Simple Script Server ---")
    print(f"Listening on {HOST}:{PORT}")
    print("Waiting for 'Update Program' request from Robot...")

    # Create a standard TCP Socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(1)
        
        # Block until the robot connects
        conn, addr = s.accept()
        with conn:
            print(f"✅ Robot connected from: {addr}")
            
            # The URScript to send. 
            # It defines a function that shows a popup on the tablet.
            script_code = """
def external_test():
    popup("Connection Successful! The Update Program button works.", "External Control Test", blocking=True)
end
"""
            print("📤 Sending script...")
            conn.sendall(script_code.encode('utf-8'))
            print("✅ Script sent. Closing connection.")

if __name__ == "__main__":
    run_server()
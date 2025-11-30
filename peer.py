import socket
import threading
import os
import sys

if len(sys.argv) > 2:
    print(f"Peer: {sys.argv[1]}")
    print(f"Port: {sys.argv[2]}")
else:
    print("Nenhum argumento foi passado.")

TRACKER = ("127.0.0.1", 8000)
PEER_ID = sys.argv[1]
PORT = int(sys.argv[2])
PEER_FILES = f"{PEER_ID}/files"

class Peer:
    def __init__(self, peer_id, port, files_dir):
        self.peer_id = peer_id
        self.port = port
        self.files_dir = files_dir
        self.registered = False
        self.peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.peer_socket.bind(("0.0.0.0", self.port))
        self.peer_socket.listen(5)
    
    def start(self):
        while True:
            connection, address = self.peer_socket.accept()
            threading.Thread(target=self.handle_request, args=(connection, address)).start()
    
    def handle_request(self, connection, address):
        data = connection.recv(4096).decode()
        command, filename = data.split()

        if command == "GET":
            path = os.path.join(self.files_dir, filename)
            with open(path, "rb") as f:
                connection.sendall(f.read())
        connection.close()
    
    def register_with_tracker(self):
        peer_id = self.peer_id
        files = ",".join(os.listdir(self.files_dir))
        port = self.port

        message = f"REGISTER 127.0.0.1 {peer_id} {port} {files}"

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(TRACKER)
            s.sendall(message.encode())
            response = s.recv(4096).decode()
            print(f"Tracker response: {response}")
            if response == "REGISTERED":
                self.registered = True
            s.close()

    def who_has(self, filename):
        message = f"WHO_HAS {filename}"

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(TRACKER)
            s.sendall(message.encode())
            response = s.recv(4096).decode()
            s.close()
            return response.split(",") if response else []

if __name__ == "__main__":
    peer = Peer(PEER_ID, PORT, PEER_FILES)
    peer.register_with_tracker()

    if peer.registered:
        peer.start()
        

    




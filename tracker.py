import socket
import threading

# Rastreador para gerenciar peers em uma rede P2P simples
class Tracker:
    def __init__(self):
        self.peers = {}
        self.lock = threading.Lock()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("0.0.0.0", 8000))
        self.server_socket.listen(5)
        
    def start(self):
        print("Tracker started on port 8000")
        while True:
            connection, address = self.server_socket.accept()
            threading.Thread(target=self.handle_request, args=(connection, address)).start()

    def handle_request(self, connection, address):
        data = connection.recv(4096).decode()
        data = data.split()

        try:
            command = data[0]

            if command == "REGISTER":
                peer_ip = data[1]
                peer_id = data[2]
                peer_port = data[3]
                files = data[4].split(",")
                with self.lock:
                    self.peers[peer_id] = {
                        "ip": peer_ip,
                        "port": peer_port,
                        "files": files
                    }

                connection.send(b"REGISTERED")
                print(f"Peer {peer_id} registered with files: {files}")
            
            elif command == "WHO_HAS":
                filename = data[1]
                holders = [
                    f"{peer_info['ip']}:{peer_info['port']}"
                    for peer_id, peer_info in self.peers.items()
                    if filename in peer_info['files']
                ]

                connection.sendall(",".join(holders).encode())
            
            elif command == "NEW_FILE":
                peer_id = data[1]
                filename = data[2]
                with self.lock:
                    if peer_id in self.peers:
                        self.peers[peer_id]['files'].append(filename)
                        print(f"Peer {peer_id} added new file: {filename}")
                connection.send(b"NEW FILE ADDED TO PEER FILES DIRECTORY")

            elif command == "DISCONNECT":
                peer_id = data[1]
                with self.lock:
                    if peer_id in self.peers:
                        del self.peers[peer_id]
                        print(f"Peer {peer_id} disconnected")

        except Exception as e:
            connection.send(b"NOT REGISTERED")

        connection.close()

if __name__ == "__main__":
    tracker = Tracker()
    tracker.start() 
        
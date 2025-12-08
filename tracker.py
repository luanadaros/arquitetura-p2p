import time
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
    
    def _verify_peer_files(self, peer_id, files):
        peer_ip = self.peers[peer_id]['ip']
        peer_port = int(self.peers[peer_id]['port'])

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((peer_ip, peer_port))
            s.sendall(f"VERIFY_FILES {','.join(files)}".encode())
            response = s.recv(4096).decode()
            if response != "FILES_OK":
                new_files = response.replace("New files list: ", "").split(",")
                with self.lock:
                    self.peers[peer_id]['files'] = new_files
                print(f"Peer {peer_id} updated files list: {new_files}")
        
    def _update_list_of_files(self):
        for peer_id in self.peers:
            self._verify_peer_files(peer_id, self.peers[peer_id]['files'])

    def _periodic_update(self):
        while True:
            try:
                self._update_list_of_files()
            except Exception as e:
                print("Error updating files:", e)
            time.sleep(2)

    def get_my_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        print("Tracker IP:", s.getsockname()[0])
        s.close()

    def start(self):
        print("Tracker started on port 8000")
        threading.Thread(target=self._periodic_update, daemon=True).start()
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
        
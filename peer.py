import socket
import threading
import os
import sys
import struct
from file import FILES

if len(sys.argv) > 2:
    print(f"Peer: {sys.argv[1]}")
    print(f"Port: {sys.argv[2]}")
else:
    print("Nenhum argumento foi passado.")

TRACKER = ("127.0.0.1", 8000)
PEER_ID = sys.argv[1]
PORT = int(sys.argv[2])
PEER_FILES = f"{PEER_ID}/files"
SIZE_BLOCK = 4096

class Peer:
    def __init__(self, peer_id, port, files_dir):
        self.peer_id = peer_id
        self.port = port

        self.files = []
        for file in os.listdir(files_dir):
            file_path = os.path.join(files_dir, file)
            if os.path.isfile(file_path):
                f = FILES(file_path)
                self.files.append(f)

        self.registered = False
        self.peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.peer_socket.bind(("0.0.0.0", self.port))
        self.peer_socket.listen(5)
    
    def start(self):
        while True:
            connection, address = self.peer_socket.accept()
            threading.Thread(target=self.handle_request, args=(connection, address)).start()
    
    def handle_request(self, connection):
        data = connection.recv(4096).decode()
        command, filename = data.split()
        
        if command == "GET":
            for f in self.files:
                if f.file_name == filename:
                    for block_idx in range(f.get_n_of_blocks()):
                        block_data = f.get_block(block_idx)
                        block_size = len(block_data)
                        header = struct.pack("!II", block_idx, block_size)
                        connection.sendall(header + block_data)
                    break
        connection.close()
    
    def _recvn(sock, n):
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data

    def request_file(self, filename):
        holders = self.who_has(filename)
        if not holders:
            print(f"Nenhum peer possui o arquivo {filename}")
            return

        ip, port = holders[0].split(":")
        port = int(port)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((ip, port))
            s.sendall(f"GET {filename}".encode())

            file = FILES()
            blocks = {}

            while True:
                header = self._recvn(s, 8)
                if not header:
                    break

                block_idx, block_size = struct.unpack("!II", header)
                block_data = self._recvn(s, block_size)
                blocks[block_idx] = block_data

            if blocks:
                for idx, data in blocks.items():
                    file._read_inblock(idx, data)
                file.order_blocks()
                file.set_n_of_blocks(len(blocks))
                file.file_name = filename
                self.files.append(file)

        print(f"Arquivo {filename} baixado com sucesso.")


    def register_with_tracker(self):
        peer_id = self.peer_id
        files_names = [file.file_name for file in self.files]

        files = ",".join(files_names)
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
        

    




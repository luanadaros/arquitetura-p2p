import socket
import threading
import os
import time
import sys
import struct
from file import FILES

if len(sys.argv) != 4:
    print("Missing arguments. Usage: python peer.py <PEER_ID> <PORT> <TRACKER_IP>")
    sys.exit(1)

TRACKER = (sys.argv[3], 8000)
PEER_ID = sys.argv[1]
PORT = int(sys.argv[2])
PEER_FILES = f"{PEER_ID}/files"
SIZE_BLOCK = 4096

class Peer:
    def __init__(self, peer_id, port, files_dir):
        self.peer_id = peer_id
        self.port = port

        self.files = self.__get_files_from_dir(files_dir)

        self.registered = False
        self._dir = files_dir
        self.peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.peer_socket.bind(("0.0.0.0", self.port))
        self.peer_socket.listen(5)
    
    def __get_files_from_dir(self, files_dir):
        files = []
        for file in os.listdir(files_dir):
            file_path = os.path.join(files_dir, file)
            if os.path.isfile(file_path):
                f = FILES(file_path)
                files.append(f)
        return files
    
    def _get_my_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip

    def start(self):
        while True:
            try:
                connection, address = self.peer_socket.accept()
                threading.Thread(target=self.handle_request, args=(connection, address)).start()
            except KeyboardInterrupt:
                print("Disconnecting peer...")
                self.peer_socket.close()
                sys.exit(0)
    
    def handle_request(self, connection, address):
        try:
            data = connection.recv(4096).decode()
        except Exception as e:
            print(f"[ERROR] Falha ao receber dados de {address}: {e}")
            connection.close()
            return

        try:
            command, filename = data.split()
        except ValueError:
            print(f"[ERROR] Comando inválido recebido: {data}")
            connection.close()
            return

        
        if command == "GET":
            for f in self.files:
                if f.file_name == filename:
                    try:

                        blocks = f.generate_blocklist()
                        total_blocks = len(blocks)
                        total_size = f.size
                        connection.sendall(struct.pack("!II", total_blocks, total_size))

                        for idx, block in blocks.items():
                            header = struct.pack("!II", idx, len(block))
                            connection.sendall(header + block)
                    except Exception as e:
                        print(f"[ERROR] Falha ao enviar arquivo {filename}: {e}")

        elif command == "VERIFY_FILES":
            requested_files = filename.split(",")
            self.files = self.__get_files_from_dir(self._dir)
            current_file_names = [f.file_name for f in self.files]

            if set(requested_files) == set(current_file_names):
                connection.sendall(b"FILES_OK")
            else:
                new_files_list = ",".join(current_file_names)
                response = f"New files list: {new_files_list}"
                connection.sendall(response.encode())
        connection.close()
    
    def _recvn(self, sock, n):
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
            print(f"No peer has the file {filename}")
            return

        blocks = {}
        blocks_lock = threading.Lock()
        meta_info = {"total_blocks": None, "total_size": None}
        meta_lock = threading.Lock()


        def download_from_peer(holder):
            ip, port = holder.split(":")
            port = int(port)

            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5)

                    # Conectar
                    try:
                        s.connect((ip, port))
                    except Exception as e:
                        print(f"[ERROR] Falha ao conectar ao peer {holder}: {e}")
                        return

                    # Mandar GET
                    try:
                        s.sendall(f"GET {filename}".encode())
                    except Exception as e:
                        print(f"[ERROR] Falha ao enviar GET para {holder}: {e}")
                        return

                    # RECEBER META-INFORMAÇÃO
                    try:
                        meta = self._recvn(s, 8)
                        if not meta:
                            print("[ERROR] meta-info vazia")
                            return

                        total_blocks, total_size = struct.unpack("!II", meta)
                        print(f"[META] Peer {holder} enviará {total_blocks} blocos (tamanho total {total_size} bytes)")

                        with meta_lock:
                            if meta_info["total_blocks"] is None:
                                meta_info["total_blocks"] = total_blocks
                                meta_info["total_size"] = total_size

                    except Exception as e:
                        print(f"[ERROR] Falha ao receber meta-info de {holder}: {e}")
                        return

                    # RECEBER BLOCOS
                    while True:
                        try:
                            header = self._recvn(s, 8)
                        except Exception as e:
                            print(f"[ERROR] Falha ao receber header de {holder}: {e}")
                            return

                        if not header:
                            break

                        try:
                            block_idx, block_size = struct.unpack("!II", header)
                            block_data = self._recvn(s, block_size)
                        except Exception as e:
                            print(f"[ERROR] Header inválido/truncado em {holder}: {e}")
                            return

                        with blocks_lock:
                            if block_idx not in blocks:
                                blocks[block_idx] = block_data
                                print(f"[RECEIVED] Bloco {block_idx} ({block_size} bytes) de {holder}")
            except Exception as e:
                print(f"[ERROR] Falha inesperada no download com peer {holder}: {e}")

        threads = []
        start_time = time.time()

        for holder in holders:
            t = threading.Thread(target=download_from_peer, args=(holder,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        end_time = time.time()
        download_time = end_time - start_time
        print(f"[DOWNLOAD COMPLETE] Time taken: {download_time:.2f} seconds")

        if not blocks:
            print(f"[ERROR] Nenhum bloco foi recebido de nenhum peer.")
            return

        file = FILES()


        try:
            file.read_from_blocklist(blocks, filename)
        except Exception as e:
            print(f"[ERROR] Falha ao reconstruir o arquivo {filename}: {e}")
            return

        expected = meta_info["total_blocks"]

        if expected is not None and len(blocks) != expected:
            missing = sorted(set(range(expected)) - set(blocks.keys()))
            print(f"[WARNING] Arquivo {filename} incompleto: faltam os blocos {missing}")
        else:
            print(f"[OK] Arquivo {filename} reconstruído com sucesso.")

        self.files.append(file)
        file.save_to_disk(f"{self.peer_id}/files")
        self.send_new_file_notification(filename)
        print(f"[DONE] File {filename} saved.")

        with open("download_times.csv", "a") as log_file:
            log_file.write(f"{filename}, {file.size}, {len(holders)}, {download_time:.2f}\n")

    def send_new_file_notification(self, filename):
        message = f"NEW_FILE {self.peer_id} {filename}"

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(TRACKER)
            s.sendall(message.encode())
            response = s.recv(4096).decode()
            print(f"Tracker response: {response}")
            s.close()

    def register_with_tracker(self):
        peer_id = self.peer_id
        files_names = [file.file_name for file in self.files]

        files = ",".join(files_names)
        port = self.port
        peer_ip = self._get_my_ip()

        message = f"REGISTER {peer_ip} {peer_id} {port} {files}"

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

    def disconnect_from_tracker(self):
        message = f"DISCONNECT {self.peer_id}"

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(TRACKER)
            s.sendall(message.encode())
            s.close()

if __name__ == "__main__":
    peer = Peer(PEER_ID, PORT, PEER_FILES)
    peer.register_with_tracker()

    if peer.registered:
        server_thread = threading.Thread(target=peer.start, daemon=True)
        server_thread.start()

        while True:
            command = input("> ").strip()

            if command.startswith("get "):
                filename = command.split(" ", 1)[1]
                peer.request_file(filename)

            elif command == "myfiles":
                for f in peer.files:
                    print("-", f.file_name)

            elif command.startswith("whohas "):
                filename = command.split(" ", 1)[1]
                holders = peer.who_has(filename)
                if holders:
                    print(f"Peers with the file {filename}:")
                    for holder in holders:
                        print("-", holder)
                else:
                    print(f"No peer has the file {filename}")

            elif command == "exit":
                print("Finishing peer connection...")
                peer.disconnect_from_tracker()
                sys.exit(0)

            else:
                print("Invalid command. Available commands: get <filename>, myfiles, whohas <filename>, exit")

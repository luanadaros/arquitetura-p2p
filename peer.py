import socket
from array import array
import threading
import os
import time
import sys
import struct
from file import FILES
from tests import benchmark, stress_test

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
    
    def _recvn_from_buffer(self, sock, n, buf):
        """Lê n bytes usando primeiro o que já está em buf; retorna (data, buf_restante)."""
        while len(buf) < n:
            packet = sock.recv(4096)
            if not packet:
                return None, b""
            buf += packet
        return buf[:n], buf[n:]

    def handle_request(self, connection, address):
        try:
            raw = connection.recv(4096)
            if not raw:
                connection.close()
                return
        except Exception as e:
            print(f"[ERROR] Falha ao receber dados de {address}: {e}")
            connection.close()
            return

        # ==========================================================
        # MODO GET_BLOCKS (robusto contra fragmentação + coalescing)
        # ==========================================================
        buf = raw

        while b"\n" not in buf and len(buf) < 4096:
            try:
                more = connection.recv(4096)
            except Exception:
                more = b""
            if not more:
                break
            buf += more

        if b"\n" in buf:
            line, rest = buf.split(b"\n", 1)

            # se for GET_BLOCKS, entra no modo especial
            if line.startswith(b"GET_BLOCKS "):
                try:
                    parts = line.decode("utf-8", errors="strict").strip().split()
                    if len(parts) != 2:
                        print(f"[ERROR] GET_BLOCKS inválido: {parts}")
                        connection.close()
                        return
                    _, filename = parts
                except Exception:
                    print("[ERROR] Linha GET_BLOCKS não decodificável/ inválida")
                    connection.close()
                    return

                # lê qty (4 bytes) do buffer/resto
                raw_qty, rest = self._recvn_from_buffer(connection, 4, rest)
                if raw_qty is None:
                    connection.close()
                    return
                qty = struct.unpack("!I", raw_qty)[0]

                if qty > 200_000:
                    print(f"> [ERROR] qty absurdo em GET_BLOCKS: {qty}")
                    connection.close()
                    return

                # lê ids (qty * 4)
                ids_bytes, rest = self._recvn_from_buffer(connection, qty * 4, rest)
                if ids_bytes is None:
                    connection.close()
                    return

                ids = array("I")
                ids.frombytes(ids_bytes)
                # chegou em network order (big-endian) -> converter pro host
                ids.byteswap()
                wanted = list(ids)

                # serve o arquivo
                f = next((x for x in self.files if x.file_name == filename), None)
                if f is None:
                    connection.close()
                    return

                blocks = f.generate_blocklist()
                total_blocks = len(blocks)
                total_size = f.size

                connection.sendall(struct.pack("!II", total_blocks, total_size))
                for idx in wanted:
                    payload = blocks.get(idx)
                    if payload is None:
                        # fecha (mantém seu comportamento) — se quiser log aqui, pode
                        connection.close()
                        return
                    connection.sendall(struct.pack("!II", idx, len(payload)))
                    connection.sendall(payload)

                connection.close()
                return

        # ==========================================================
        # FLUXO ANTIGO (GET / VERIFY_FILES / BLOCK_COUNT etc.)
        # ==========================================================
        try:
            data = raw.decode()
        except Exception as e:
            print(f"[ERROR] decode falhou de {address}: {e}")
            connection.close()
            return

        try:
            command, filename = data.split()
        except ValueError:
            print(f"[ERROR] Comando inválido recebido: {data}")
            connection.close()
            return

        # ... GET / BLOCK_COUNT etc ...

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
        
        elif command == "BLOCK_COUNT":
            for f in self.files:
                if f.file_name == filename:
                    response = f"OK {f.n_of_blocks}\n"
                    connection.sendall(response.encode())
                    break
        
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
        holders = self.who_has(filename)  # [{"addr": "...", "blocks": N}, ...]
        if not holders:
            print(f"No peer has the file {filename}")
            return

        # 1) valida block_count
        unique_counts = sorted({h["blocks"] for h in holders if isinstance(h.get("blocks"), int)})
        if not unique_counts:
            print("[ERROR] WHO_HAS não retornou block_count válido.")
            return

        if len(unique_counts) > 1:
            print(f"[WARNING] Peers reportaram números diferentes de blocos para '{filename}': {unique_counts}")
            print("Escolha qual block_count você quer usar:")
            for i, bc in enumerate(unique_counts, 1):
                print(f"  {i}) {bc} blocos")

            while True:
                try:
                    choice = int(input("Digite o número da opção: ").strip())
                    if 1 <= choice <= len(unique_counts):
                        chosen_blocks = unique_counts[choice - 1]
                        break
                except ValueError:
                    pass
                print("Opção inválida.")
        else:
            chosen_blocks = unique_counts[0]

        # 2) filtra peers compatíveis com o chosen_blocks
        selected_peers = [h for h in holders if h.get("blocks") == chosen_blocks]
        if not selected_peers:
            print("[ERROR] Nenhum peer compatível com o block_count escolhido.")
            return

        # 3) divide blocos 0..N-1 entre peers (round-robin)
        assignments = {h["addr"]: [] for h in selected_peers}
        peer_addrs = [h["addr"] for h in selected_peers]
        for block_idx in range(chosen_blocks):
            addr = peer_addrs[block_idx % len(peer_addrs)]
            assignments[addr].append(block_idx)

        blocks = {}
        blocks_lock = threading.Lock()
        meta_info = {"total_blocks": chosen_blocks, "total_size": None}
        meta_lock = threading.Lock()

        def download_from_peer(addr: str, wanted_blocks: list[int]):
            if not wanted_blocks:
                return

            ip, port = addr.split(":")
            port = int(port)

            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5)
                    try:
                        s.connect((ip, port))
                    except Exception as e:
                        print(f"[ERROR] Falha ao conectar ao peer {addr}: {e}")
                        return

                    # 4) novo comando: GET_BLOCKS <filename> <qtd> <id0> <id1> ...
                    try:
                        # comando em texto TERMINADO EM \n
                        s.sendall(f"GET_BLOCKS {filename}\n".encode("utf-8"))

                        # binário: qty + ids
                        s.sendall(struct.pack("!I", len(wanted_blocks)))
                        s.sendall(b"".join(struct.pack("!I", b) for b in wanted_blocks))


                    except Exception as e:
                        print(f"[ERROR] Falha ao enviar GET_BLOCKS para {addr}: {e}")
                        return

                    # 5) meta-info (8 bytes) igual antes (total_blocks,total_size)
                    try:
                        meta = self._recvn(s, 8)
                        if not meta:
                            print(f"[ERROR] meta-info vazia de {addr}")
                            return
                        total_blocks, total_size = struct.unpack("!II", meta)

                        # guarda total_size uma vez
                        with meta_lock:
                            if meta_info["total_size"] is None:
                                meta_info["total_size"] = total_size

                        # (opcional) sanity check
                        if total_blocks != chosen_blocks:
                            print(f"[WARNING] Peer {addr} informou total_blocks={total_blocks}, esperado={chosen_blocks}")

                    except Exception as e:
                        print(f"[ERROR] Falha ao receber meta-info de {addr}: {e}")
                        return

                    # 6) recebe exatamente len(wanted_blocks) blocos
                    # protocolo: para cada bloco -> header(8) [idx,size] + data(size)
                    for _ in range(len(wanted_blocks)):
                        try:
                            header = self._recvn(s, 8)
                            if not header:
                                print(f"[ERROR] Conexão fechou cedo por {addr}")
                                return
                            block_idx, block_size = struct.unpack("!II", header)
                            block_data = self._recvn(s, block_size)
                            if block_data is None or len(block_data) != block_size:
                                print(f"[ERROR] Bloco truncado {block_idx} vindo de {addr}")
                                return
                        except Exception as e:
                            print(f"[ERROR] Falha ao receber bloco de {addr}: {e}")
                            return

                        with blocks_lock:
                            # evita sobrescrever caso chegue duplicado
                            if block_idx not in blocks:
                                blocks[block_idx] = block_data
                                print(f"[RECEIVED] Bloco {block_idx} ({block_size} bytes) de {addr}")

            except Exception as e:
                print(f"[ERROR] Falha inesperada no download com peer {addr}: {e}")

        # ---- roda paralelo ----
        threads = []
        start_time = time.time()

        for addr, wanted in assignments.items():
            t = threading.Thread(target=download_from_peer, args=(addr, wanted))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        download_time = time.time() - start_time
        print(f"[DOWNLOAD COMPLETE] Time taken: {download_time:.2f} seconds")

        if not blocks:
            print("[ERROR] Nenhum bloco foi recebido de nenhum peer.")
            return

        # 7) checa faltantes
        expected = meta_info["total_blocks"]
        if expected is not None and len(blocks) != expected:
            missing = sorted(set(range(expected)) - set(blocks.keys()))
            print(f"[WARNING] Arquivo {filename} incompleto: faltam os blocos {missing}")
            return  # você pode optar por continuar e salvar parcial, mas aqui eu interrompo.

        # 8) reconstrói e salva
        file = FILES()
        try:
            file.read_from_blocklist(blocks, filename)
        except Exception as e:
            print(f"[ERROR] Falha ao reconstruir o arquivo {filename}: {e}")
            return

        self.files.append(file)
        file.save_to_disk(f"{self.peer_id}/files")
        self.send_new_file_notification(filename)
        print(f"[DONE] File {filename} saved.")

        # 9) log
        csv_path = "download_times.csv"
        file_exists = os.path.exists(csv_path)
        with open(csv_path, "a", encoding="utf-8") as log_file:
            if not file_exists:
                log_file.write("arquivo,tamanho,n_peers,tempo\n")
            log_file.write(f"{filename},{file.size},{len(selected_peers)},{download_time:.2f}\n")
    
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

        peers = []
        if response:
            for entry in response.split(","):
                addr, blocks = entry.split("|")
                peers.append({
                    "addr": addr,
                    "blocks": int(blocks)
                })

        return peers

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

            elif command.startswith("bench "):
                parts = command.split()
                if len(parts) == 2:
                    filename = parts[1]
                    runs = 5 
                elif len(parts) == 3:
                    filename = parts[1]
                    try:
                        runs = int(parts[2])
                    except ValueError:
                        print("Uso: bench <filename> [runs]")
                        continue
                else:
                    print("Uso: bench <filename> [runs]")
                    continue

                benchmark(peer, filename, runs)

            elif command.startswith("stress "):
                parts = command.split()
                if len(parts) == 2:
                    filename = parts[1]
                    n_threads = 10  # default
                elif len(parts) == 3:
                    filename = parts[1]
                    try:
                        n_threads = int(parts[2])
                    except ValueError:
                        print("Uso: stress <filename> [n_threads]")
                        continue
                else:
                    print("Uso: stress <filename> [n_threads]")
                    continue

                stress_test(peer, filename, n_threads)

            elif command == "exit":
                print("Finishing peer connection...")
                peer.disconnect_from_tracker()
                sys.exit(0)

            else:
                print("Invalid command. Available commands: get <filename>, myfiles, whohas <filename>, bench <filename> [runs], stress <filename> [n_threads], exit")

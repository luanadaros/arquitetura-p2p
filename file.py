import os
BLOCK_SIZE = 4096

class FILES:
    def __init__(self, file_path: str = None):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path) if file_path else ""
        self.n_of_blocks = 0
        self.size = 0
        self._blocks = {}
        if file_path:
            self._read_from_file(file_path)
        
    def _read_from_file(self, file_path: str):
        idx = 0
        with open(file_path, 'rb') as f:
            while True:
                block = f.read(BLOCK_SIZE)
                if not block:
                    break
                self._blocks[idx] = {'idx': idx, 'data': block}
                idx += 1

            self.size = os.path.getsize(file_path)
        self.n_of_blocks = idx
    
    def _read_inblock(self, idx: int, block: bytes):
        if len(block) > BLOCK_SIZE:
            raise ValueError(f"Block size must be less than or equal to {BLOCK_SIZE} bytes")
        self._blocks[idx] = {'idx': idx, 'data': block}

    def read_from_blocklist(self, blocklist: dict, file_name: str):
        self.file_name = file_name
        for idx, block in blocklist.items():
            self._read_inblock(idx, block)
            self.size += len(block)
        self.order_blocks()
        self.n_of_blocks = len(self._blocks)
        self.order_blocks()

    def set_n_of_blocks(self, n: int):
        if n> 0 and n <= len(self._blocks):
            self.n_of_blocks = n

    def get_block(self, idx: int) -> bytes:
        if idx in self._blocks:
            return self._blocks[idx]['data']
        else:
            raise IndexError("Block index out of range")

    def order_blocks(self): 
        #ordena pelos indices
        self._blocks = dict(sorted(self._blocks.items()))

    def get_n_of_blocks(self) -> int:
        return len(self._blocks)

    def save_to_disk(self, directory: str):
        if not os.path.exists(directory):
            os.makedirs(directory)

        file_path = os.path.join(directory, self.file_name)

        with open(file_path, 'wb') as f:
            for idx in range(self.n_of_blocks):
                f.write(self._blocks[idx]['data'])
# tests.py
import time
import threading

def benchmark(peer, filename, runs=5):
    """
    Executa o download do arquivo várias vezes em sequência
    e mede o tempo de cada execução.
    """
    tempos = []

    print(f"\n=== BENCHMARK: {filename} ({runs} execuções) ===")
    for i in range(runs):
        print(f"\n[RUN {i+1}/{runs}]")
        inicio = time.time()
        peer.request_file(filename)  # já mede tempo interno e loga no CSV
        fim = time.time()
        dur = fim - inicio
        tempos.append(dur)
        print(f"[RUN {i+1}] Tempo total (externo): {dur:.2f} s")

    media = sum(tempos) / len(tempos)
    print("\n=== RESULTADO BENCHMARK ===")
    print("Tempos individuais:", ", ".join(f"{t:.2f}s" for t in tempos))
    print(f"Média: {media:.2f}s")


def stress_test(peer, filename, n_threads=10):
    """
    Dispara vários downloads em paralelo para testar estabilidade
    sob carga (muitos clientes pedindo o mesmo arquivo).
    """
    print(f"\n=== STRESS TEST: {filename} com {n_threads} clientes em paralelo ===")

    def worker(idx):
        try:
            print(f"[THREAD {idx}] Iniciando download...")
            peer.request_file(filename)
            print(f"[THREAD {idx}] Download finalizado.")
        except Exception as e:
            print(f"[THREAD {idx}] ERRO: {e}")

    threads = []
    inicio = time.time()

    for i in range(n_threads):
        t = threading.Thread(target=worker, args=(i,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    fim = time.time()
    dur = fim - inicio
    print(f"\n=== STRESS TEST FINALIZADO ===")
    print(f"Tempo total para {n_threads} downloads paralelos: {dur:.2f}s")

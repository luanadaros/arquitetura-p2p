import csv
from collections import defaultdict
import statistics
import matplotlib.pyplot as plt

CSV_PATH = "download_times.csv"

def load_data(csv_path=CSV_PATH):
    """
    Lê CSV com cabeçalho:
    arquivo  tamanho  n_peers  tempo

    Aceita qualquer combinação de espaços/tabs como separador.
    """
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split()  # separa por qualquer whitespace (espaço, tab, etc.)

            # pula a linha de cabeçalho
            if parts[0].lower() == "arquivo":
                continue

            if len(parts) < 4:
                # linha quebrada ou com menos colunas
                continue

            try:
                filename = parts[0]
                size_bytes = int(parts[1])
                n_peers = int(parts[2])
                time_sec = float(parts[3])
            except ValueError:
                # se der erro na conversão, ignora a linha
                continue

            rows.append((filename, size_bytes, n_peers, time_sec))

    return rows


def aggregate_by_peers(rows):
    times_by_peers = defaultdict(list)

    for filename, size_bytes, n_peers, time_sec in rows:
        times_by_peers[n_peers].append(time_sec)

    peers_list = sorted(times_by_peers.keys())
    means = []
    stds = []

    for n in peers_list:
        ts = times_by_peers[n]
        mean_t = statistics.mean(ts)
        std_t = statistics.pstdev(ts) if len(ts) > 1 else 0.0
        means.append(mean_t)
        stds.append(std_t)

    return peers_list, means, stds

def plot_performance(peers_list, means, stds):
    plt.figure()
    x = range(len(peers_list))

    plt.bar(x, means, yerr=stds, capsize=5)
    plt.xticks(x, peers_list)

    plt.xlabel("Número de peers com o arquivo")
    plt.ylabel("Tempo médio de download (s)")
    plt.title("Tempo de download em função do número de peers")
    plt.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig("resultado_desempenho.png", dpi=150)
    plt.show()

def main():
    rows = load_data()
    if not rows:
        print("Nenhum dado válido encontrado no CSV.")
        return

    peers_list, means, stds = aggregate_by_peers(rows)

    print("\nResumo dos resultados:")
    for n, m, s in zip(peers_list, means, stds):
        print(f"{n} peers -> média: {m:.2f}s | desvio: {s:.2f}s")

    plot_performance(peers_list, means, stds)

if __name__ == "__main__":
    main()

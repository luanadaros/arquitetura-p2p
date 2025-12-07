# Arquitetura P2P para Compartilhamento de Arquivos
Este projeto implementa uma rede P2P básica com troca de arquivos divididos em blocos em uma rede local.
Ele é composto por dois tipos de processos:

🔹 Tracker → Responsável por registrar peers e armazenar quem possui quais arquivos

🔹 Peer → Cada peer possui seus próprios arquivos, baixa arquivos de outros peers e notifica o tracker quando recebe novos

## 📌 Estrutura do Projeto
```bash 
/project_root
├── tracker.py        # Servidor central de registro (Tracker)
├── peer.py           # Implementação de um peer
└── file.py           # Manipulação de arquivos por blocos
```

Cada peer deve possuir um diretório próprio contendo seus arquivos:

```
peer_id/
└── files/
      ├── arquivo1.txt
      ├── imagem.jpg
      └── ...

```

## 🚀 Execução do Projeto
### 1. Iniciar o Tracker
O tracker é o servidor central que administra os peers ativos. 
```bash
python tracker.py
```
Ele inicia automaticamente na porta local **8000** e fica ouvindo conexões.

### 2. Iniciar um Peer
Cada peer deve ser iniciado com:

```bash
python peer.py <PEER_ID> <PORT>
```

Exemplo:

```bash
python peer.py A 9000
python peer.py B 9001
```

**Requisitos:**

✔ O diretório ``<PEER_ID>/files`` deve existir

✔ Todos os arquivos dentro dele serão registrados no tracker ao iniciar

## 📂 Principais Funcionalidades
| Componente          | Função                                                                                      |
| ------------------- | ------------------------------------------------------------------------------------------- |
| **Tracker**         | Recebe registro de peers, consulta quem possui arquivos e atualiza novos arquivos recebidos |
| **Peer**            | Troca blocos de arquivos com outros peers e reconstrói arquivos recebidos                   |
| **Files (file.py)** | Fragmenta e reconstrói arquivos em blocos de até 4096 bytes (4kB)                                |


## 🔧 Comandos Disponíveis no Peer
Dentro do terminal do Peer:
| Comando             | Função                                            |
| ------------------- | ------------------------------------------------- |
| `get <filename>`    | Baixa um arquivo de outros peers que o possuem    |
| `myfiles`           | Lista arquivos locais do peer                     |
| `whohas <filename>` | Pergunta ao tracker quais peers possuem o arquivo |
| `exit`              | Encerra o peer e desconecta do tracker            |


## 📥 Processo de Download (Resumo Interno)

1. Peer → pergunta ao tracker quem possui o arquivo

2. Para cada peer com o arquivo → abre conexão TCP

3. O peer requisitante recebe o arquivo em blocos

4. Reconstrói o arquivo localmente

5. Salva em ``<peer_id>/files/``

6. Notifica o tracker com **NEW_FILE**

## 🧪 Exemplo de Execução
[Vídeo: executando peers](./src/exemplo.mp4)

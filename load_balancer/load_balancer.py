import socket
import sys
import threading
from datetime import datetime
import logging
import os

os.makedirs("load_balancer/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    filename="load_balancer/logs/load_balancers.log",
)

class LoadBalancer:
    def __init__(self, listen_host='localhost', listen_port=4000, servers=None, lb_id=1):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.servers = servers or [('localhost', 5000), ('localhost', 5001)]
        self.lb_id = lb_id
        self.current_server_index = 0
        self.lock = threading.Lock()  # para garantir acesso seguro ao índice

    def get_timestamp(self):
        return datetime.now().isoformat()

    def calculate_delay(self, ts1, ts2):
        dt1 = datetime.fromisoformat(ts1)
        dt2 = datetime.fromisoformat(ts2)
        return (dt2 - dt1).total_seconds() * 1000  # Convertendo para milissegundos

    def get_next_server(self):
        with self.lock:
            server = self.servers[self.current_server_index]
            self.current_server_index = (self.current_server_index + 1) % len(self.servers)
        return server

    def handle_client(self, client_conn):
        while True:
            data = client_conn.recv(1024)
            if not data:
                break

            decoded = data.decode()
            parts = decoded.strip().strip(";").split(";")

            if len(parts) < 3:
                print(f"[LB-{self.lb_id}] Mensagem malformada: {decoded}")
                logging.error(f"[LB-{self.lb_id}] Mensagem malformada: {decoded}")
                continue

            # O último timestamp é do nó anterior
            ts_anterior = parts[-1]
            ts_recv = self.get_timestamp()
            delay = self.calculate_delay(ts_anterior, ts_recv)
            ts_send = self.get_timestamp()

            # Constrói a nova parte com os dados deste nó
            nova_parte = f"{ts_recv};{delay:.6f};{ts_send}"

            # Concatena tudo
            message_to_server = f"{decoded.strip()};{nova_parte}"

            server_host, server_port = self.get_next_server()
            print(f"[LB-{self.lb_id}] Encaminhando para servidor {server_host}:{server_port}: {message_to_server}")
            logging.info(f"[LB-{self.lb_id}] Encaminhando para servidor {server_host}:{server_port}: {message_to_server}")

            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_conn:
                    server_conn.connect((server_host, server_port))
                    server_conn.sendall(message_to_server.encode())

                    # Recebe resposta e envia de volta ao cliente
                    response = server_conn.recv(1024)
                    client_conn.sendall(response)

            except ConnectionRefusedError:
                print(f"[LB-{self.lb_id}] Erro: servidor {server_host}:{server_port} indisponível")
                logging.error(f"[LB-{self.lb_id}] Erro: servidor {server_host}:{server_port} indisponível")
                client_conn.sendall(f"{server_host}:{server_port} indisponível".encode("utf-8"))

    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind((self.listen_host, self.listen_port))
            listener.listen()
            print(f"[LB-{self.lb_id}] Aguardando cliente em {self.listen_host}:{self.listen_port}...")
            logging.info(f"[LB-{self.lb_id}] Aguardando cliente em {self.listen_host}:{self.listen_port}...")

            while True:
                client_conn, addr = listener.accept()
                print(f"[LB-{self.lb_id}] Conectado com {addr}")
                logging.info(f"[LB-{self.lb_id}] Conectado com {addr}")
                threading.Thread(target=self.handle_client, args=(client_conn,)).start()

def parse_servers(servers_str):
    """
    Recebe string no formato host1:port1,host2:port2,...
    Retorna lista de tuplas (host, int(port))
    """
    servers = []
    for server in servers_str.split(","):
        host, port = server.split(":")
        servers.append((host, int(port)))
    return servers

if __name__ == "__main__":
    listen_host = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("LISTEN_HOST", "localhost")
    listen_port = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("LISTEN_PORT", 4000))
    servers_str = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("SERVERS", "localhost:5000,localhost:5001")
    servers = parse_servers(servers_str)
    lb_id = int(sys.argv[4]) if len(sys.argv) > 4 else int(os.environ.get("LB_ID", 1))

    lb = LoadBalancer(listen_host=listen_host, listen_port=listen_port, servers=servers, lb_id=lb_id)
    try:
        lb.start()
    except KeyboardInterrupt:
        print(f"\n[LB-{lb_id}] Encerrando...")


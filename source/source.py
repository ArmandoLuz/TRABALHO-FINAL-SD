import socket
import sys
import time
from datetime import datetime
import logging
import os

os.makedirs("source/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    filename="source/logs/sources.log",
)

class Source:
    def __init__(self, host='localhost', port=4000):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.num_ciclo = 1
        self.mrt = 0
        self.std = 0
        self.mean_response_times = []

    def get_timestamp(self):
        return datetime.now().isoformat()

    def connect(self):
        self.socket.connect((self.host, self.port))
        print(f"[SOURCE] Conectado ao LoadBalancer em {self.host}:{self.port}")
        logging.info(f"[SOURCE] Conectado ao LoadBalancer em {self.host}:{self.port}")

    def send_messages(self, total_messages=5):
        for num_msg in range(1, total_messages + 1):
            origin_ts = self.get_timestamp()
            message = f"{self.num_ciclo};{num_msg};{origin_ts};"
            self.socket.sendall(message.encode())
            print(f"[SOURCE] -> [LB]: {message}")
            logging.info(f"[SOURCE] -> [LB]: {message}")

            response = self.socket.recv(1024).decode()
            print(f"[SOURCE] <- [SERVICE]: {response}")
            logging.info(f"[SOURCE] <- [SERVICE]: {response}")
            self.mean_response_times.append(self.extract_mean_response_time(response))
            time.sleep(1)

        self.mrt = sum(self.mean_response_times) / len(self.mean_response_times)
        print(f"[SOURCE] Tempo médio de resposta (MRT): {self.mrt} ms")
        logging.info(f"[SOURCE] Tempo médio de resposta (MRT): {self.mrt} ms")
        self.std = self.calculate_std(self.mean_response_times)
        print(f"[SOURCE] Desvio padrão (STD): {self.std} ms")
        logging.info(f"[SOURCE] Desvio padrão (STD): {self.std} ms")


    def extract_mean_response_time(self, response):
        try:
            parts = response.split(";")
            parts = [part.strip() for part in parts if part.strip()]
            mean_response_time = 0
            mean_response_time += float(parts[4])
            mean_response_time += float(parts[7])
            mean_response_time += float(parts[10])
            mean_response_time += float(parts[13])
            return mean_response_time / 4

        except Exception:
            print("[SOURCE] Erro ao extrair o tempo de resposta da mensagem")
            logging.error("[SOURCE] Erro ao extrair o tempo de resposta da mensagem")
            return 0

    def calculate_std(self, response_times):
        if len(response_times) < 2:
            return 0

        mean = sum(response_times) / len(response_times)
        variance = sum((x - mean) ** 2 for x in response_times) / (len(response_times) - 1)
        return variance ** 0.5

    def close(self):
        self.socket.close()

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("HOST", "lb1")
    port = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("PORT", 4000))
    print(f"[SOURCE] Conectando ao LoadBalancer em {host}:{port}")
    logging.info(f"[SOURCE] Conectando ao LoadBalancer:{port} em 15 segundos")
    time.sleep(15)

    Source = Source(host=host, port=port)
    try:
        Source.connect()
        Source.send_messages()
    except KeyboardInterrupt:
        print("\n[SOURCE] Encerrando...")
    finally:
        Source.close()

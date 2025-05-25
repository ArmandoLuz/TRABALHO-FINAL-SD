import socket
import sys
from datetime import datetime
import logging
import os
import numpy as np
from tensorflow.keras.applications.mobilenet_v2 import (
    MobileNetV2, preprocess_input, decode_predictions
)
from tensorflow.keras.preprocessing import image
from PIL import Image

os.makedirs("service/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    filename="service/logs/services.log",
)

# Função para inferir uma imagem
def run_inference_on_images(image_dir, model):
    results = []

    for filename in os.listdir(image_dir):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            img_path = os.path.join(image_dir, filename)
            img = image.load_img(img_path, target_size=(224, 224))

            x = image.img_to_array(img)
            x = np.expand_dims(x, axis=0)
            x = preprocess_input(x)

            preds = model.predict(x)
            decoded = decode_predictions(preds, top=1)[0][0]  # top prediction
            results.append((filename, decoded[1], float(decoded[2])))

    return results

class Service:
    def __init__(self, host='localhost', port=5000, forward_host=None, forward_port=None):
        self.host = host
        self.port = port
        self.forward_host = forward_host
        self.forward_port = forward_port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.model = MobileNetV2(weights='imagenet')
        self.image_dir = "./data"  # Caminho da base de imagens

    def get_timestamp(self):
        return datetime.now().isoformat()

    def calculate_delay(self, origin_ts, current_ts):
        origin_dt = datetime.fromisoformat(origin_ts)
        current_dt = datetime.fromisoformat(current_ts)
        return (current_dt - origin_dt).total_seconds() * 1000  # Convertendo para milissegundos

    def forward_message(self, message):
        """
        Envia a mensagem para o endereço forward e retorna a resposta.
        Se não tiver forward configurado, retorna None.
        """
        if not self.forward_host or not self.forward_port:
            return None

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as forward_sock:
                forward_sock.connect((self.forward_host, self.forward_port))
                forward_sock.sendall(message.encode())
                response = forward_sock.recv(1024)
                return response.decode()
        except ConnectionRefusedError:
            print(f"[SERVICE-{self.port}] Erro: forward Service {self.forward_host}:{self.forward_port} indisponível")
            logging.error(f"[SERVICE-{self.port}] Erro: forward Service {self.forward_host}:{self.forward_port} indisponível")
            return None

    def start(self):
        self.socket.bind((self.host, self.port))
        self.socket.listen()
        print(f"[SERVICE-{self.port}] Aguardando conexão em {self.host}:{self.port}...")
        logging.info(f"[SERVICE-{self.port}] Aguardando conexão em {self.host}:{self.port}...")

        while True:
            conn, addr = self.socket.accept()
            with conn:
                print(f"[SERVICE-{self.port}] Conectado com {addr}")
                logging.info(f"[SERVICE-{self.port}] Conectado com {addr}")
                data = conn.recv(1024)
                if not data:
                    continue

                results = run_inference_on_images(self.image_dir, self.model) # Roda o modelo MobileNetV2 para inferir as imagens da base de dados
                print(f"[SERVICE-{self.port}] Resultados da inferência: {results}")
                logging.info(f"[SERVICE-{self.port}] Resultados da inferência: {results}")

                decoded = data.decode()
                parts = decoded.strip().strip(";").split(";")

                if len(parts) < 3:
                    print(f"[SERVICE-{self.port}] Mensagem malformada: {decoded}")
                    logging.error(f"[SERVICE-{self.port}] Mensagem malformada: {decoded}")
                    continue

                ts_anterior = parts[-1]
                ts_recv = self.get_timestamp()
                delay = self.calculate_delay(ts_anterior, ts_recv)
                ts_send = self.get_timestamp()

                nova_parte = f"{ts_recv};{delay:.6f};{ts_send}"
                mensagem_completa = f"{decoded.strip()};{nova_parte}"

                # Se houver servidor para encaminhar, repassa a mensagem
                response_from_forward = None
                if self.forward_host and self.forward_port:
                    response_from_forward = self.forward_message(mensagem_completa)

                # Se recebeu resposta do forward, pode optar por devolver ela ao cliente ou a própria resposta local.
                # Aqui retorno a resposta do forward, caso exista.
                to_send = response_from_forward if response_from_forward else mensagem_completa

                print(f"[SERVICE-{self.port}] Respondendo: {to_send}")
                logging.info(f"[SERVICE-{self.port}] Respondendo: {to_send}")
                conn.sendall(to_send.encode())

    def close(self):
        self.socket.close()

if __name__ == "__main__":
    # Tenta pegar do sys.argv (linha de comando)
    host = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SERVICE_HOST", "localhost")
    port = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("SERVICE_PORT", 5000))
    forward_host = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("FORWARD_HOST")
    forward_port = int(sys.argv[4]) if len(sys.argv) > 4 else (
        int(os.environ.get("FORWARD_PORT")) if os.environ.get("FORWARD_PORT") else None
    )

    service = Service(host=host, port=port, forward_host=forward_host, forward_port=forward_port)
    try:
        service.start()
    except KeyboardInterrupt:
        print("\n[SERVICE] Encerrando...")


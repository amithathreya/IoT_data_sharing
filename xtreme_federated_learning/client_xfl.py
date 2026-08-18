import ssl
import json
import time
import os
import pika
import oqs
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import tensorflow as tf
import numpy as np
import pandas as pd
import psutil
import pickle
import base64
import threading

# ── Anomaly Detection Model ────────────────────────────────────
def get_model(input_shape=(20,)):
    model = tf.keras.models.Sequential([
        tf.keras.layers.Reshape((1, input_shape[0]), input_shape=input_shape),
        tf.keras.layers.SimpleRNN(256, return_sequences=True, name="rnn_1"),
        tf.keras.layers.SimpleRNN(128, return_sequences=True, name="rnn_2"),
        tf.keras.layers.SimpleRNN(64, name="rnn_3"),
        tf.keras.layers.Dense(9, activation="softmax", name="output")
    ])
    model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
    return model

def gather_sensor_data(num_samples=8):
    print(f"[Client] Gathering {num_samples} real sensor samples for training. This will take ~{num_samples * 2.5} seconds...")
    X_train = []
    y_train = []
    
    local_buffer = []
    while len(X_train) < num_samples:
        try:
            with open("/sys/bus/iio/devices/iio:device0/in_temp_input", "r") as f:
                temp_val = float(f.read().strip()) / 1000.0
            with open("/sys/bus/iio/devices/iio:device0/in_humidityrelative_input", "r") as f:
                hum_val = float(f.read().strip()) / 1000.0
        except Exception as e:
            # Fallback to mock values if IIO files aren't ready
            temp_val = 27.5
            hum_val = 76.0
            
        local_buffer.extend([temp_val, hum_val])
        if len(local_buffer) > 20:
            local_buffer = local_buffer[-20:]
            
        if len(local_buffer) == 20:
            X_train.append(list(local_buffer))
            y_train.append(0) # Class 0 = Normal
            
        time.sleep(2.5)
        
    # --- Inject Synthetic Anomalies ---
    # To teach the Neural Network what an anomaly looks like, we generate fake "bad" data
    num_anomalies = num_samples // 2
    for _ in range(num_anomalies):
        anomaly_sequence = []
        # Generate a Normal baseline first (e.g. ~29C, ~60% hum)
        normal_temp = 29.0 + float(np.random.uniform(-1, 1))
        normal_hum = 60.0 + float(np.random.uniform(-2, 2))
        
        # Decide how many readings at the end will be a sudden spike (1 to 10 readings)
        spike_length = np.random.randint(1, 11)
        
        # Determine the extreme values for the spike
        spike_temp = float(np.random.choice([np.random.randint(-10, 15), np.random.randint(35, 80)]))
        spike_hum = float(np.random.choice([np.random.randint(0, 40), np.random.randint(75, 100)]))
        
        for i in range(10):
            if i >= (10 - spike_length):
                # We hit the spike!
                rand_temp = spike_temp + float(np.random.uniform(-1, 1))
                rand_hum = spike_hum + float(np.random.uniform(-2, 2))
            else:
                # Still in the normal part of the sequence
                rand_temp = normal_temp + float(np.random.uniform(-0.5, 0.5))
                rand_hum = normal_hum + float(np.random.uniform(-1, 1))
                
            anomaly_sequence.extend([rand_temp, rand_hum])
            
        X_train.append(anomaly_sequence)
        # Randomly assign it to an Anomaly Class (1 through 8)
        y_train.append(int(np.random.randint(1, 9)))
        
    x_train_np = np.array(X_train) / 100.0
    y_train_np = tf.keras.utils.to_categorical(np.array(y_train), num_classes=9)
    return x_train_np, y_train_np

# ── AMQP & PQC Config ──────────────────────────────────────────
BROKER_HOST   = "127.0.0.1"
BROKER_PORT   = 5671
AMQP_USER     = "pqc_user"
AMQP_PASSWORD = "pqc_password"
EXCHANGE_UPDATES = "fl_updates"
EXCHANGE_GLOBAL  = "fl_global"

# Paths
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CERT_DIR      = os.path.join(os.path.dirname(BASE_DIR), "certs")
CA_CERT       = os.path.join(CERT_DIR, "ca_certificate.pem")
CLIENT_CERT   = os.path.join(CERT_DIR, "server_certificate.pem")
CLIENT_KEY    = os.path.join(CERT_DIR, "server_key.pem")
SERVER_PUB    = os.path.join(CERT_DIR, "server_kem_pub.key")
KEM_KEY_PATH  = os.path.join(CERT_DIR, "consumer_kem_priv.key")

def make_tls_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_verify_locations(CA_CERT)
    ctx.load_cert_chain(CLIENT_CERT, CLIENT_KEY)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx

def serialize_weights(weights):
    return base64.b64encode(pickle.dumps(weights)).decode('utf-8')

def deserialize_weights(b64_str):
    return pickle.loads(base64.b64decode(b64_str))

class FederatedClient:
    def __init__(self, cid):
        self.cid = cid
        self.model = get_model()
        # Data is now gathered dynamically before training
        self.channel = None
        
        # Publisher ML-DSA-65 Signer
        self.publisher_signer = oqs.Signature("ML-DSA-65")
        self.PUB_SIG_KEY = self.publisher_signer.generate_keypair()
        self.PRIV_SIG_KEY = self.publisher_signer.export_secret_key()
        
        with open(SERVER_PUB, "rb") as f:
            self.SERVER_KEM_PUB = f.read()

        if os.path.exists(KEM_KEY_PATH):
            with open(KEM_KEY_PATH, "rb") as f:
                self.CONSUMER_KEM_PRIV = f.read()
        else:
            self.CONSUMER_KEM_PRIV = None

    def start(self):
        print(f"[Client {self.cid}] Connecting to RabbitMQ...")
        tls_ctx = make_tls_context()
        params = pika.ConnectionParameters(
            host=BROKER_HOST, port=BROKER_PORT, virtual_host="/",
            credentials=pika.PlainCredentials(AMQP_USER, AMQP_PASSWORD),
            ssl_options=pika.SSLOptions(tls_ctx, BROKER_HOST)
        )
        conn = pika.BlockingConnection(params)
        self.channel = conn.channel()
        
        self.channel.exchange_declare(exchange=EXCHANGE_UPDATES, exchange_type="fanout", durable=True)
        self.channel.exchange_declare(exchange=EXCHANGE_GLOBAL, exchange_type="fanout", durable=True)
        
        result = self.channel.queue_declare(queue="", exclusive=True)
        self.channel.queue_bind(exchange=EXCHANGE_GLOBAL, queue=result.method.queue)
        self.channel.basic_consume(queue=result.method.queue, on_message_callback=self.on_global_weights)

        threading.Thread(target=self.train_and_send).start()

        print(f"[Client {self.cid}] Waiting for global FL updates...")
        self.channel.start_consuming()

    def train_and_send(self):
        self.x_train, self.y_train = gather_sensor_data(num_samples=8)
        print(f"[Client {self.cid}] Starting local training on real data...")
        self.model.fit(self.x_train, self.y_train, epochs=2, batch_size=8, verbose=1)
        
        weights_out = os.path.join(BASE_DIR, "local_model.weights.h5")
        try:
            self.model.save_weights(weights_out)
            print(f"[Client {self.cid}] Saved updated weights to {weights_out} for publisher.")
        except Exception as e:
            print(f"[Client] Could not save weights: {e}")

        weights_data = serialize_weights(self.model.get_weights())
        payload = json.dumps({"cid": self.cid, "weights": weights_data}).encode()

        with oqs.KeyEncapsulation("ML-KEM-768") as kem:
            kem_ciphertext, shared_secret = kem.encap_secret(self.SERVER_KEM_PUB)

        aesgcm = AESGCM(shared_secret[:32])
        nonce = os.urandom(12)
        encrypted_payload = aesgcm.encrypt(nonce, payload, None)

        auth_data = kem_ciphertext + nonce + encrypted_payload
        with oqs.Signature("ML-DSA-65", self.PRIV_SIG_KEY) as signer:
            signature = signer.sign(auth_data)

        envelope = json.dumps({
            "kem_cipher": kem_ciphertext.hex(),
            "nonce": nonce.hex(),
            "enc_payload": encrypted_payload.hex(),
            "signature": signature.hex(),
            "pub_sig_key": self.PUB_SIG_KEY.hex()
        }).encode()

        def publish_message():
            self.channel.basic_publish(
                exchange=EXCHANGE_UPDATES,
                routing_key="",
                body=envelope,
                properties=pika.BasicProperties(content_type="application/json", delivery_mode=2)
            )
            print(f"[Client {self.cid}] Sent encrypted weights to server.")
            
        self.channel.connection.add_callback_threadsafe(publish_message)

    def on_global_weights(self, ch, method, properties, body):
        print(f"\n[Client {self.cid}] Received new global weights!")
        envelope = json.loads(body)

        kem_cipher   = bytes.fromhex(envelope["kem_cipher"])
        nonce        = bytes.fromhex(envelope["nonce"])
        enc_payload  = bytes.fromhex(envelope["enc_payload"])
        signature    = bytes.fromhex(envelope["signature"])
        pub_sig_key  = bytes.fromhex(envelope["pub_sig_key"])

        auth_data = kem_cipher + nonce + enc_payload
        with oqs.Signature("ML-DSA-65") as verifier:
            if not verifier.verify(auth_data, signature, pub_sig_key):
                print(" ❌ INVALID SIGNATURE from Server!\n")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

        # Server broadcasts use a random AES key passed in kem_cipher (TLS secures the link)
        shared_secret = kem_cipher

        aesgcm = AESGCM(shared_secret[:32])
        try:
            decrypted_bytes = aesgcm.decrypt(nonce, enc_payload, None)
            data = json.loads(decrypted_bytes)
        except Exception as e:
            print(f" ❌ Decryption failed: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        global_weights = deserialize_weights(data["weights"])
        self.model.set_weights(global_weights)
        
        weights_out = os.path.join(os.path.dirname(BASE_DIR), "pi_files", "local_model_weights.h5")
        if os.path.exists(os.path.dirname(weights_out)):
            self.model.save_weights(weights_out)
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
        threading.Thread(target=self.train_and_send).start()

if __name__ == "__main__":
    try:
        cid_input = input("Enter your client rank (0 for Client 1, 1 for Client 2, etc.) [Default 0]: ")
        cid = int(cid_input) if cid_input.strip() else 0
    except:
        cid = 0
    client = FederatedClient(cid)
    client.start()

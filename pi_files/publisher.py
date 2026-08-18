import ssl
import json
import time
import os
import oqs
import pika
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import tensorflow as tf
import numpy as np

# ── Anomaly Detection Model (Edge Inference) ───────────────────
def get_anomaly_model(input_shape=(20,)):
    model = tf.keras.models.Sequential([
        tf.keras.layers.Reshape((1, input_shape[0]), input_shape=input_shape),
        tf.keras.layers.SimpleRNN(256, return_sequences=True, name="rnn_1"),
        tf.keras.layers.SimpleRNN(128, return_sequences=True, name="rnn_2"),
        tf.keras.layers.SimpleRNN(64, name="rnn_3"),
        tf.keras.layers.Dense(9, activation="softmax", name="output")
    ])
    model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
    return model

print("[Publisher] Initializing Local Anomaly Detection Model...")
anomaly_model = get_anomaly_model()
# Try loading federated weights if available
weights_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_model.weights.h5")
last_mtime = 0
if os.path.exists(weights_path):
    print(f"[Publisher] Loading trained weights from {weights_path}")
    try:
        anomaly_model.load_weights(weights_path)
        last_mtime = os.path.getmtime(weights_path)
    except Exception as e:
        print(f"[Publisher] ⚠️ Failed to load initial weights: {e}")
else:
    print("[Publisher] No pre-trained weights found. Using random initialization.")

local_buffer = []  # Store last 10 (temp, hum) pairs
# ───────────────────────────────────────────────────────────────

# ── Configuration (Raspberry Pi) ─────────────────────────────
BROKER_HOST   = "127.0.0.1"  # Updated for local testing (change to your Windows IP if running on Pi)
BROKER_PORT   = 5671
AMQP_USER     = "pqc_user"
AMQP_PASSWORD = "pqc_password"
EXCHANGE_NAME = "sensors"

# Relative Linux paths (assuming the 'certs' folder is in the same directory)
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CERT_DIR      = os.path.join(BASE_DIR, "certs")
CA_CERT       = os.path.join(CERT_DIR, "ca_certificate.pem")
CLIENT_CERT   = os.path.join(CERT_DIR, "server_certificate.pem")
CLIENT_KEY    = os.path.join(CERT_DIR, "server_key.pem")
SERVER_PUB    = os.path.join(CERT_DIR, "server_kem_pub.key")

# ── Post-Quantum Setup ─────────────────────────────────────────
# Publisher ML-DSA-65 Signer (Generates new signature keys per session)
publisher_signer = oqs.Signature("ML-DSA-65")
PUB_SIG_KEY      = publisher_signer.generate_keypair()
PRIV_SIG_KEY     = publisher_signer.export_secret_key()


NODE_ID = os.getenv("NODE_NAME","UNIDENTIFIED_NODE")

# Load Server's ML-KEM Public Key
print("[Publisher] Loading Server's ML-KEM Public Key...")
with open(SERVER_PUB, "rb") as f:
    SERVER_KEM_PUB = f.read()

def make_tls_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_verify_locations(CA_CERT)
    ctx.load_cert_chain(CLIENT_CERT, CLIENT_KEY)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx

def main():
    print(f"[Publisher] Connecting to RabbitMQ at {BROKER_HOST} via TLS 1.3...")
    tls_ctx = make_tls_context()
    params = pika.ConnectionParameters(
        host=BROKER_HOST, port=BROKER_PORT, virtual_host="/",
        credentials=pika.PlainCredentials(AMQP_USER, AMQP_PASSWORD),
        ssl_options=pika.SSLOptions(tls_ctx, BROKER_HOST)
    )
    conn = pika.BlockingConnection(params)
    channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="fanout", durable=True)

    print("[Publisher] Publishing ML-KEM encrypted & ML-DSA signed packets...\n")
    global last_mtime
    global local_buffer
    try:
        while True:
            # ── Check for updated federated weights ──
            if os.path.exists(weights_path):
                current_mtime = os.path.getmtime(weights_path)
                if current_mtime > last_mtime:
                    print(f"\n[Publisher] 🔄 Detected updated federated weights! Reloading model...")
                    try:
                        anomaly_model.load_weights(weights_path)
                        last_mtime = current_mtime
                    except Exception as e:
                        print(f"[Publisher] ⚠️ Failed to load weights (file might be locked), will retry: {e}")

            # 1. Telemetry Payload - Reading from DHT11 Kernel Overlay (IIO)
            try:
                with open("/sys/bus/iio/devices/iio:device0/in_temp_input", "r") as f:
                    temp_val = float(f.read().strip()) / 1000.0
                with open("/sys/bus/iio/devices/iio:device0/in_humidityrelative_input", "r") as f:
                    hum_val = float(f.read().strip()) / 1000.0
            except Exception as e:
                # Fallback to mock values if the IIO files aren't ready or overlay isn't loaded
                print(f"[Sensor Error] Failed to read from sysfs: {e}")
                temp_val = 27.5
                hum_val = 76.0
            
            # ── Edge Anomaly Inference ──
            local_buffer.extend([temp_val, hum_val])
            if len(local_buffer) > 20:
                local_buffer = local_buffer[-20:]
                
            predicted_class = 0
            if len(local_buffer) == 20:
                input_data = (np.array(local_buffer) / 100.0).reshape(1, 20)
                prediction = anomaly_model.predict(input_data, verbose=0)
                predicted_class = int(np.argmax(prediction, axis=1)[0])
            # ────────────────────────────
            
            payload_data = {
                "node_id": NODE_ID,
                "temperature": temp_val,
                "humidity": hum_val,
                "timestamp_ns": time.time_ns(),
                "anomaly_class": predicted_class
            }
            payload_bytes = json.dumps(payload_data).encode()

            # 2. ML-KEM-768 Encapsulation
            with oqs.KeyEncapsulation("ML-KEM-768") as kem:
                kem_ciphertext, shared_secret = kem.encap_secret(SERVER_KEM_PUB)

            # 3. AES-256-GCM Encryption
            aesgcm = AESGCM(shared_secret[:32])
            nonce = os.urandom(12)
            encrypted_payload = aesgcm.encrypt(nonce, payload_bytes, None)

            # 4. ML-DSA-65 Signature
            auth_data = kem_ciphertext + nonce + encrypted_payload
            with oqs.Signature("ML-DSA-65", PRIV_SIG_KEY) as signer:
                signature = signer.sign(auth_data)

            # 5. Build and Publish Envelope
            envelope = json.dumps({
                "kem_cipher": kem_ciphertext.hex(),
                "nonce": nonce.hex(),
                "enc_payload": encrypted_payload.hex(),
                "signature": signature.hex(),
                "pub_sig_key": PUB_SIG_KEY.hex()
            }).encode()

            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key="",
                body=envelope,
                properties=pika.BasicProperties(content_type="application/json", delivery_mode=2)
            )
            print(f"[Publisher] Sent Secured Telemetry | Temp: {payload_data['temperature']}°C | Hum: {payload_data['humidity']}%")
            time.sleep(2.5)

    except KeyboardInterrupt:
        print("\n[Publisher] Stopping transmission...")
        conn.close()

if __name__ == "__main__":
    main()

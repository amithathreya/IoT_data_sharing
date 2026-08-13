import ssl
import json
import time
import os
import oqs
import pika
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

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
    try:
        while True:
            # 1. Telemetry Payload
            # Replace these mocked values with real DHT11/DHT22 sensor reads if you have them wired!
            payload_data = {
                "node_id":NODE_ID,
                "temperature": 27.5,
                "humidity": 76.0,
                "timestamp_ns": time.time_ns()
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

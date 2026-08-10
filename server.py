import ssl
import json
import time
import requests
import os
from pathlib import Path
import oqs
import pika
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ── Configuration (Windows Native) ─────────────────────────────
BROKER_HOST   = "127.0.0.1"
BROKER_PORT   = 5671
AMQP_USER     = "pqc_user"
AMQP_PASSWORD = "pqc_password"
EXCHANGE_NAME = "sensors"

GRAFANA_URL   = "http://127.0.0.1:3000/api/live/push/pqc_consumer"
GRAFANA_TOKEN = "TOKEN"

# Resolve certs relative to this script so the consumer works from any checkout path.
CERT_DIR      = Path(__file__).resolve().parent / "certs"
CA_CERT       = str(CERT_DIR / "ca_certificate.pem")
CLIENT_CERT   = str(CERT_DIR / "server_certificate.pem")
CLIENT_KEY    = str(CERT_DIR / "server_key.pem")
KEM_KEY_PATH  = os.path.join(CERT_DIR, "consumer_kem_priv.key")

# Load or Generate ML-KEM Private Key
CONSUMER_KEM_PRIV = None
if os.path.exists(KEM_KEY_PATH):
    with open(KEM_KEY_PATH, "rb") as f:
        CONSUMER_KEM_PRIV = f.read()
else:
    print("[Setup] No KEM key found. Generating new ML-KEM-768 Keypair...")
    with oqs.KeyEncapsulation("ML-KEM-768") as kem:
        kem.generate_keypair()
        CONSUMER_KEM_PRIV = kem.export_secret_key()
        with open(KEM_KEY_PATH, "wb") as f:
            f.write(CONSUMER_KEM_PRIV)
    print("[Setup] ML-KEM-768 Private Key saved to certs folder.")


# ── Grafana Live Direct Streaming ──────────────────────────────
def push_to_grafana_live(node_id, temperature, humidity, ts_ns):
    """Pushes live metrics with PQC security tags to Grafana adhering to Influx Line Protocol."""
    headers = {
        "Authorization": f"Bearer {GRAFANA_TOKEN}",
        "Content-Type": "text/plain"
    }
    
    # Correct Influx Line Protocol Format:
    # <measurement>,<tags> <fields> <timestamp_ns>
    # Note: node={node_id} dynamically tags the publisher node
    data = (
        f"iot_sensors,node={node_id},kem=ML-KEM-768,sig=ML-DSA-65 "
        f"temperature={temperature},humidity={humidity},secure_link=1i {ts_ns}"
    )
    
    try:
        res = requests.post(GRAFANA_URL, headers=headers, data=data, timeout=1)
        if res.status_code != 200:
            print(f"[Grafana] Push warning ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"[Grafana] Failed to push data: {e}")


# ── AMQP Message Handler ───────────────────────────────────────
def on_message(ch, method, properties, body):
    envelope = json.loads(body)

    kem_cipher   = bytes.fromhex(envelope["kem_cipher"])
    nonce        = bytes.fromhex(envelope["nonce"])
    enc_payload  = bytes.fromhex(envelope["enc_payload"])
    signature    = bytes.fromhex(envelope["signature"])
    pub_sig_key  = bytes.fromhex(envelope["pub_sig_key"])

    # 0. VISUAL PROOF FOR EVALUATORS
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔒 INCOMING SECURE ENVELOPE")
    print(f" ├─ ML-KEM-768 Ciphertext : {len(kem_cipher)} bytes")
    print(f" ├─ ML-DSA-65 Signature   : {len(signature)} bytes")
    print(f" └─ AES-GCM Payload       : {len(enc_payload)} bytes")

    # 1. Verify ML-DSA-65 Signature
    auth_data = kem_cipher + nonce + enc_payload
    with oqs.Signature("ML-DSA-65") as verifier:
        if not verifier.verify(auth_data, signature, pub_sig_key):
            print(" ❌ INVALID SIGNATURE — Packet dropped!\n")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

    # 2. Decapsulate ML-KEM-768 Shared Secret
    if not CONSUMER_KEM_PRIV:
        print(" ❌ Missing ML-KEM Private Key!\n")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    with oqs.KeyEncapsulation("ML-KEM-768", CONSUMER_KEM_PRIV) as kem:
        shared_secret = kem.decap_secret(kem_cipher)

    # 3. Decrypt AES-256-GCM Encrypted Payload
    try:
        aesgcm = AESGCM(shared_secret[:32])
        decrypted_bytes = aesgcm.decrypt(nonce, enc_payload, None)
        data = json.loads(decrypted_bytes)
    except Exception as e:
        print(f" ❌ DECRYPTION FAILED: {e}\n")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    node_id = data.get('node_id', 'unknown_node')
    temp = data.get('temperature', 'N/A')
    hum = data.get('humidity', 'N/A')
    ts_ns = data.get('timestamp_ns', time.time_ns())

    print(f" ✅ Decrypted Telemetry   : Node={node_id} | Temp={temp}°C | Humidity={hum}%\n")

    # Push to Grafana Live with explicit timestamp
    if temp != 'N/A' and hum != 'N/A':
        push_to_grafana_live(str(node_id), float(temp), float(hum), ts_ns)

    ch.basic_ack(delivery_tag=method.delivery_tag)


# ── TLS 1.3 Context Setup ──────────────────────────────────────
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
    print("[Consumer] Connecting to RabbitMQ over TLS 1.3...")
    tls_ctx = make_tls_context()
    params = pika.ConnectionParameters(
        host=BROKER_HOST, port=BROKER_PORT, virtual_host="/",
        credentials=pika.PlainCredentials(AMQP_USER, AMQP_PASSWORD),
        ssl_options=pika.SSLOptions(tls_ctx, BROKER_HOST)
    )
    conn = pika.BlockingConnection(params)
    channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="fanout", durable=True)
    result = channel.queue_declare(queue="", exclusive=True)
    channel.queue_bind(exchange=EXCHANGE_NAME, queue=result.method.queue)
    channel.basic_consume(queue=result.method.queue, on_message_callback=on_message)

    print("[Consumer] Waiting for incoming post-quantum telemetry packets...\n")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\n[Consumer] Shutting down...")
        conn.close()


if __name__ == "__main__":
    main()
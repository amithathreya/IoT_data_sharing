import ssl
import json
import time
import requests
import os
import hashlib
from web3 import Web3
from web3.exceptions import Web3Exception
from dotenv import load_dotenv
from pathlib import Path
import oqs
import pika
import sys
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

load_dotenv()

# ── Configuration (Windows Native) ─────────────────────────────
BROKER_HOST   = "127.0.0.1"
BROKER_PORT   = 5671
AMQP_USER     = "pqc_user"
AMQP_PASSWORD = "pqc_password"
EXCHANGE_NAME = "sensors"

GRAFANA_URL   = "http://localhost:3000/api/live/push/pqc_consume"
GRAFANA_TOKEN = os.getenv("GRAFANA_TOKEN")

# ── Blockchain Configuration ───────────────────────────────────
BESU_RPC_URL = "http://127.0.0.1:8545"
w3 = Web3(Web3.HTTPProvider(BESU_RPC_URL))

# Ensure these environment variables are set with your deployed contract info
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "0x0000000000000000000000000000000000000000")
BESU_PRIVATE_KEY = os.getenv("BESU_PRIVATE_KEY", "0x0000000000000000000000000000000000000000000000000000000000000000")

try:
    BESU_ACCOUNT = w3.eth.account.from_key(BESU_PRIVATE_KEY)
except Exception:
    BESU_ACCOUNT = None

# Load the full ABI from contract_abi.json
try:
    with open("contract_abi.json", "r") as f:
        CONTRACT_ABI = json.load(f)
except Exception:
    print("[Blockchain] Missing contract_abi.json")
    CONTRACT_ABI = []

if w3.is_connected() and BESU_ACCOUNT:
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
else:
    contract = None

def log_to_blockchain(node_id, ts_ns, payload_hash_bytes):
    """Logs the telemetry hash to the Besu blockchain."""
    if not w3.is_connected() or not contract or not BESU_ACCOUNT:
        print("[Blockchain] Skipped logging: Node disconnected or not configured.")
        return

    try:
        # Build the transaction
        tx = contract.functions.recordTelemetry(
            str(node_id),
            int(ts_ns),
            payload_hash_bytes
        ).build_transaction({
            'chainId': w3.eth.chain_id,
            'from': BESU_ACCOUNT.address,
            'nonce': w3.eth.get_transaction_count(BESU_ACCOUNT.address, 'pending'),
            'gas': 3000000,
            'gasPrice': w3.eth.gas_price
        })

        # Sign the transaction
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=BESU_PRIVATE_KEY)

        # Send the transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hex = w3.to_hex(tx_hash)
        # Suppressed console log for clean output
        return tx_hex
    except Exception as e:
        print(f"[Blockchain] Failed to log telemetry: {e}")
        return None

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


# ── Dashboard Direct Streaming ──────────────────────────────
DASHBOARD_URL = "http://localhost:4000/api/data"

def push_to_dashboard(payload):
    """Pushes live metrics, anomalies, and blockchain logs to the unified React dashboard."""
    headers = {
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(DASHBOARD_URL, headers=headers, json=payload, timeout=2)
        return "OK" if res.status_code == 200 else str(res.status_code)
    except Exception:
        return "ERR"


# ── AMQP Message Handler ───────────────────────────────────────
def on_message(ch, method, properties, body):
    envelope = json.loads(body)

    kem_cipher   = bytes.fromhex(envelope["kem_cipher"])
    nonce        = bytes.fromhex(envelope["nonce"])
    enc_payload  = bytes.fromhex(envelope["enc_payload"])
    signature    = bytes.fromhex(envelope["signature"])
    pub_sig_key  = bytes.fromhex(envelope["pub_sig_key"])

    # Processing Incoming Secure Envelope silently

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

    # Hash the payload
    payload_str = json.dumps(data, sort_keys=True).encode('utf-8')
    payload_hash = hashlib.sha256(payload_str).digest()

    # Log hash to blockchain
    tx_hash = log_to_blockchain(node_id, ts_ns, payload_hash)

    # ── Anomaly Detection Alert ──────────────────────────────────
    anomaly_class = data.get('anomaly_class', 0)
    if anomaly_class > 0:
        print(f"\n🚨 [ANOMALY DETECTED] Node {node_id} exhibited anomalous behavior! (Class: {anomaly_class}) 🚨")
    # ───────────────────────────────────────────────────────────────

    dashboard_status = "Skip"
    # Push everything to the React dashboard backend
    dashboard_payload = {
        "node_id": str(node_id),
        "temperature": temp if temp == 'N/A' else float(temp),
        "humidity": hum if hum == 'N/A' else float(hum),
        "anomaly_class": anomaly_class,
        "ts_ns": ts_ns,
        "payload_hash": payload_hash.hex(),
        "tx_hash": tx_hash if tx_hash else "[Besu Not Connected / Tx Failed]"
    }
        
    dashboard_status = push_to_dashboard(dashboard_payload)

    # In-place console log using \r
    short_tx = f"{tx_hash[:6]}..{tx_hash[-4:]}" if tx_hash else "None"
    sys.stdout.write(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✅ Node: {node_id} | {temp}°C | {hum}% | Tx: {short_tx} | Dashboard: {dashboard_status} {' '*5}")
    sys.stdout.flush()

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
import json
import hashlib
import oqs
import pika
import time
import threading
import requests
from datetime import datetime
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account

# ── Configuration ──────────────────────────────────────────────
BROKER_HOST   = "127.0.0.1"
BROKER_PORT   = 5672
AMQP_USER     = "pqc_user"
AMQP_PASSWORD = "pqc_password"
EXCHANGE_NAME = "sensors"
NODE_ID       = "pi-node-1"
PRIVATE_KEY   = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"

# Grafana Live Direct Streaming Configuration
GRAFANA_URL   = "http://192.168.29.73:3000/api/live/push/pqc_consumer"
GRAFANA_TOKEN = "glsa_Mi7Dg19vZB71D2cP0FdzqamxrTvwpcMM_108c7017" # Match the token you created earlier

# ── Blockchain setup ───────────────────────────────────────────
w3 = Web3(Web3.HTTPProvider("http://localhost:8545"))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
assert w3.is_connected(), "Cannot connect to Besu"
account  = Account.from_key(PRIVATE_KEY)
deployer = account.address

with open("/home/amith/pqc_project/blockchain/contract.json") as f:
    info = json.load(f)

contract = w3.eth.contract(address=info["address"], abi=info["abi"])

# ── Manual nonce manager ───────────────────────────────────────
nonce_lock    = threading.Lock()
current_nonce = w3.eth.get_transaction_count(deployer)
print(f"[Consumer] Starting nonce: {current_nonce}")

def get_next_nonce():
    global current_nonce
    with nonce_lock:
        nonce = current_nonce
        current_nonce += 1
        return nonce

print(f"[Consumer] Besu block:  {w3.eth.block_number}")
print(f"[Consumer] Contract:    {info['address']}")
print(f"[Consumer] Account:     {deployer}")

# ── Grafana Live Streaming Function ───────────────────────────
def push_to_grafana_live(temperature, humidity):
    """Pushes live metrics straight to Grafana Live from the consumer node."""
    headers = {
        "Authorization": f"Bearer {GRAFANA_TOKEN}",
        "Content-Type": "text/plain"
    }

    # Grab the exact current time in nanoseconds
    timestamp_ns = time.time_ns()

    # Strict Influx Line Protocol: measurement,tags fields timestamp
    data = f"iot_sensors,node={NODE_ID} temperature={temperature},humidity={humidity} {timestamp_ns}"

    try:
        requests.post(GRAFANA_URL, headers=headers, data=data, timeout=1)
    except Exception as e:
        print(f"[Consumer] Grafana push failed: {e}")

# ── Signature verification ─────────────────────────────────────
def verify_signature(envelope: dict) -> bool:
    try:
        payload   = json.dumps(envelope["payload"]).encode()
        signature = bytes.fromhex(envelope["signature"])
        pub_key   = bytes.fromhex(envelope["pub_key"])
        with oqs.Signature("ML-DSA-65") as verifier:
            return verifier.verify(payload, signature, pub_key)
    except Exception as e:
        print(f"[Consumer] Sig error: {e}")
        return False

# ── Async blockchain submission ────────────────────────────────
def submit_to_blockchain(body: bytes, ts: str):
    try:
        sha256_hash = hashlib.sha256(body).digest()
        nonce       = get_next_nonce()

        tx = contract.functions.storeRecord(
            NODE_ID,
            sha256_hash,
            int(time.time())
        ).build_transaction({
            "from":      deployer,
            "nonce":     nonce,
            "gas":       200000,
            "gasPrice": 0,
        })
        signed  = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

        receipt  = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        verified = contract.functions.verifyRecord(sha256_hash).call()
        total    = contract.functions.getTotalRecords().call()

        print(f"            ⛓  [{ts}] block={receipt['blockNumber']} "
              f"verified={verified} total={total}")

    except Exception as e:
        print(f"            ⛓  [{ts}] ERROR: {e}")

# ── Message handler ────────────────────────────────────────────
def on_message(ch, method, properties, body):
    envelope = json.loads(body)

    if not verify_signature(envelope):
        print("[Consumer] ⚠  INVALID SIGNATURE — rejected")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    data = envelope["payload"]
    ts   = datetime.now().strftime("%H:%M:%S")

    temp = data.get('temperature', 'N/A')
    hum = data.get('humidity', 'N/A')

    print(f"[Consumer] ✓ {ts} | "
          f"temp={temp}°C  |  "
          f"humidity={hum}%")

    # Push to Grafana Live instantly upon message verification
    if temp != 'N/A' and hum != 'N/A':
        push_to_grafana_live(float(temp), float(hum))

    threading.Thread(
        target=submit_to_blockchain,
        args=(body, ts),
        daemon=True
    ).start()

    ch.basic_ack(delivery_tag=method.delivery_tag)

# ── AMQP connection ────────────────────────────────────────────
def main():
    params  = pika.ConnectionParameters(
        host=BROKER_HOST, port=BROKER_PORT, virtual_host="/",
        credentials=pika.PlainCredentials(AMQP_USER, AMQP_PASSWORD))
    conn    = pika.BlockingConnection(params)
    channel = conn.channel()
    channel.exchange_declare(
        exchange=EXCHANGE_NAME, exchange_type="fanout", durable=True)
    result = channel.queue_declare(queue="", exclusive=True)
    channel.queue_bind(exchange=EXCHANGE_NAME, queue=result.method.queue)
    channel.basic_consume(
        queue=result.method.queue, on_message_callback=on_message)
    print("[Consumer] Waiting for messages...\n")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        conn.close()

if __name__ == "__main__":
    main()

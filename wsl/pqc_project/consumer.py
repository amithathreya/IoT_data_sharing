import json
import hashlib
import oqs
import pika
import time
import threading
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
# We track nonce in memory and increment it locally after each tx
# This prevents multiple threads from getting the same nonce
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
            "from":     deployer,
            "nonce":    nonce,
            "gas":      200000,
            "gasPrice": 0,
        })
        signed  = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

        receipt  = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        verified = contract.functions.verifyRecord(sha256_hash).call()
        total    = contract.functions.getTotalRecords().call()

        print(f"           ⛓  [{ts}] block={receipt['blockNumber']} "
              f"verified={verified} total={total}")

    except Exception as e:
        print(f"           ⛓  [{ts}] ERROR: {e}")

# ── Message handler ────────────────────────────────────────────
def on_message(ch, method, properties, body):
    envelope = json.loads(body)

    if not verify_signature(envelope):
        print("[Consumer] ⚠  INVALID SIGNATURE — rejected")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    data = envelope["payload"]
    ts   = datetime.now().strftime("%H:%M:%S")

    print(f"[Consumer] ✓ {ts} | "
          f"temp={data['temperature']}°C  "
          f"humidity={data['humidity']}%  "
          f"pressure={data['pressure']}hPa")

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

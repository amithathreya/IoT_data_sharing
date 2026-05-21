import ssl
import json
import oqs
import pika
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────
BROKER_HOST   = "127.0.0.1"   # Consumer connects via localhost (same machine as nginx)
BROKER_PORT   = 5672
AMQP_USER     = "pqc_user"
AMQP_PASSWORD = "pqc_password"
EXCHANGE_NAME = "sensors"

CERT_DIR    = "/home/amith/pqc-certs"
CA_CERT     = f"{CERT_DIR}/ca.crt"
CLIENT_CERT = f"{CERT_DIR}/client.crt"
CLIENT_KEY  = f"{CERT_DIR}/client.key"

# ── TLS context ────────────────────────────────────────────────
def make_tls_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_verify_locations(CA_CERT)
    ctx.load_cert_chain(CLIENT_CERT, CLIENT_KEY)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx

# ── Signature verification ─────────────────────────────────────
def verify_signature(envelope: dict) -> bool:
    try:
        payload   = json.dumps(envelope["payload"]).encode()
        signature = bytes.fromhex(envelope["signature"])
        pub_key   = bytes.fromhex(envelope["pub_key"])
        with oqs.Signature("ML-DSA-65") as verifier:
            return verifier.verify(payload, signature, pub_key)
    except Exception as e:
        print(f"[Consumer] Verification error: {e}")
        return False

# ── Message handler ────────────────────────────────────────────
def on_message(ch, method, properties, body):
    envelope = json.loads(body)

    if not verify_signature(envelope):
        print("[Consumer] ⚠  INVALID SIGNATURE — message rejected")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    data = envelope["payload"]
    ts   = datetime.now().strftime("%H:%M:%S")
    print(f"[Consumer] ✓ {ts} | "
          f"temp={data['temperature']}°C  "
          f"humidity={data['humidity']}%  "
          f"pressure={data['pressure']}hPa")
    ch.basic_ack(delivery_tag=method.delivery_tag)

# ── AMQP connection ────────────────────────────────────────────
def connect() -> pika.BlockingConnection:
    params = pika.ConnectionParameters(
        host         = BROKER_HOST,
        port         = BROKER_PORT,
        virtual_host = "/",
        credentials  = pika.PlainCredentials(AMQP_USER, AMQP_PASSWORD),
    )
    return pika.BlockingConnection(params)
# ── Main ───────────────────────────────────────────────────────
def main():
    print("[Consumer] Connecting to broker...")
    conn    = connect()
    channel = conn.channel()

    channel.exchange_declare(
        exchange      = EXCHANGE_NAME,
        exchange_type = "fanout",
        durable       = True,
    )

    # Exclusive queue — deleted when consumer disconnects
    result = channel.queue_declare(queue="", exclusive=True)
    queue_name = result.method.queue

    channel.queue_bind(exchange=EXCHANGE_NAME, queue=queue_name)
    channel.basic_consume(queue=queue_name, on_message_callback=on_message)

    print("[Consumer] Waiting for messages. Press Ctrl+C to stop.\n")
    print(f"  {'Time':<10} {'Temp':>8} {'Humidity':>10} {'Pressure':>12}")
    print(f"  {'─'*10} {'─'*8} {'─'*10} {'─'*12}")

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\n[Consumer] Stopped.")
        conn.close()

if __name__ == "__main__":
    main()

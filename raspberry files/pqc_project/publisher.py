import ssl
import json
import time
import oqs
import pika

# ── Configuration ──────────────────────────────────────────────
BROKER_HOST   = "192.168.29.73"   # Your PC's IP
BROKER_PORT   = 5671
AMQP_USER     = "pqc_user"
AMQP_PASSWORD = "pqc_password"
EXCHANGE_NAME = "sensors"

CERT_DIR      = "/home/test_pi/pqc-certs"
CA_CERT       = f"{CERT_DIR}/ca.crt"
CLIENT_CERT   = f"{CERT_DIR}/client.crt"
CLIENT_KEY    = f"{CERT_DIR}/client.key"

# ── PQC signing setup ──────────────────────────────────────────
# Generate a keypair once at startup
# In production you would load these from disk
_signer          = oqs.Signature("ML-DSA-65")
PUBLIC_KEY       = _signer.generate_keypair()
SECRET_KEY       = _signer.export_secret_key()

def sign_payload(payload_bytes: bytes) -> str:
    """Sign payload with ML-DSA-65, return hex-encoded signature."""
    with oqs.Signature("ML-DSA-65", SECRET_KEY) as signer:
        signature = signer.sign(payload_bytes)
    return signature.hex()

# ── TLS context ────────────────────────────────────────────────
def make_tls_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_verify_locations(CA_CERT)
    ctx.load_cert_chain(CLIENT_CERT, CLIENT_KEY)
    # Hostname checking — must match CN in broker.crt
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx

# ── AMQP connection ────────────────────────────────────────────
def connect() -> pika.BlockingConnection:
    tls_ctx  = make_tls_context()
    ssl_opts = pika.SSLOptions(tls_ctx, BROKER_HOST)
    params   = pika.ConnectionParameters(
        host        = BROKER_HOST,
        port        = BROKER_PORT,
        virtual_host= "/",
        credentials = pika.PlainCredentials(AMQP_USER, AMQP_PASSWORD),
        ssl_options = ssl_opts,
    )
    return pika.BlockingConnection(params)

# ── Sensor reading ─────────────────────────────────────────────
def read_sensors() -> dict:
    # Replace with real GPIO/I2C sensor calls
    import random
    return {
        "temperature": round(22 + random.uniform(-1, 5), 2),
        "humidity":    round(55 + random.uniform(-3, 8), 2),
        "pressure":    round(1013 + random.uniform(-2, 2), 2),
    }

# ── Main publish loop ──────────────────────────────────────────
def main():
    print("[Publisher] Connecting to broker...")
    conn    = connect()
    channel = conn.channel()

    channel.exchange_declare(
        exchange      = EXCHANGE_NAME,
        exchange_type = "fanout",
        durable       = True,
    )
    print(f"[Publisher] Connected. Streaming to exchange '{EXCHANGE_NAME}'...")
    print(f"[Publisher] Public key (first 16 bytes): {PUBLIC_KEY.hex()[:32]}...")

    while True:
        # 1. Read sensor
        reading = read_sensors()
        payload = json.dumps(reading).encode()

        # 2. Sign payload
        signature = sign_payload(payload)

        # 3. Build envelope
        envelope = json.dumps({
            "payload":   reading,
            "signature": signature,
            "pub_key":   PUBLIC_KEY.hex(),
        }).encode()

        # 4. Publish
        channel.basic_publish(
            exchange    = EXCHANGE_NAME,
            routing_key = "",
            body        = envelope,
            properties  = pika.BasicProperties(
                content_type  = "application/json",
                delivery_mode = 2,
            ),
        )
        print(f"[Publisher] Sent: {reading}")
        time.sleep(1)

if __name__ == "__main__":
    main()

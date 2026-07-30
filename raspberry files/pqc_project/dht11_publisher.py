import ssl
import json
import time
import os
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

# DHT11 Sysfs Paths (Linux driver mappings)
TEMP_PATH = "/sys/bus/iio/devices/iio:device0/in_temp_input"
HUM_PATH  = "/sys/bus/iio/devices/iio:device0/in_humidityrelative_input"

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
def read_sensor_file(file_path):
    """Reads the raw file and returns the float value divided by 1000."""
    try:
        if not os.path.exists(file_path):
            return None
        with open(file_path, "r") as f:
            raw_value = f.read().strip()
            return float(raw_value) / 1000.0
    except (IOError, ValueError):
        # Handles momentary hardware read hiccups gracefully
        return None

def read_dht11() -> dict:
    """Reads actual values from the DHT11 sysfs files."""
    temperature = read_sensor_file(TEMP_PATH)
    humidity = read_sensor_file(HUM_PATH)

    if temperature is not None and humidity is not None:
        return {
            "temperature": round(temperature, 1),
            "humidity": round(humidity, 1)
        }
    return None

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
    print("-" * 50)

    try:
        while True:
            # 1. Read sensor
            reading = read_dht11()

            if reading is None:
                print("[Publisher] Reading failed or sensor busy... retrying.")
                # Always wait 2.5s before querying hardware again
                time.sleep(2.5)
                continue

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
            print(f"[Publisher] Sent: Temp: {reading['temperature']}°C  |  Humidity: {reading['humidity']}%")

            # 5. Respect hardware polling limits
            time.sleep(2.5)

    except KeyboardInterrupt:
        print("\n[Publisher] Script stopped by user.")
        conn.close()

if __name__ == "__main__":
    main(

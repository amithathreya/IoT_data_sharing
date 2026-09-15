import ssl
import json
import time
import os
import oqs
import pika
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ── Configuration (Raspberry Pi Audio Publisher) ─────────────────────────────
BROKER_HOST   = "127.0.0.1"
BROKER_PORT   = 5671
AMQP_USER     = "pqc_user"
AMQP_PASSWORD = "pqc_password"
EXCHANGE_NAME = "audio_stream"

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CERT_DIR      = os.path.join(BASE_DIR, "certs")
CA_CERT       = os.path.join(CERT_DIR, "ca_certificate.pem")
CLIENT_CERT   = os.path.join(CERT_DIR, "server_certificate.pem")
CLIENT_KEY    = os.path.join(CERT_DIR, "server_key.pem")
SERVER_PUB    = os.path.join(CERT_DIR, "server_kem_pub.key")

AUDIO_DIR = os.path.join(BASE_DIR, "audio_out")
CHUNK_SIZE = 64 * 1024  # 64 KB per chunk

publisher_signer = oqs.Signature("ML-DSA-65")
PUB_SIG_KEY      = publisher_signer.generate_keypair()
PRIV_SIG_KEY     = publisher_signer.export_secret_key()

NODE_ID = os.getenv("NODE_NAME", "UNIDENTIFIED_NODE")

print("[AudioPublisher] Loading Server's ML-KEM Public Key...")
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
    print(f"[AudioPublisher] Connecting to RabbitMQ at {BROKER_HOST} via TLS 1.3...")
    tls_ctx = make_tls_context()
    params = pika.ConnectionParameters(
        host=BROKER_HOST, port=BROKER_PORT, virtual_host="/",
        credentials=pika.PlainCredentials(AMQP_USER, AMQP_PASSWORD),
        ssl_options=pika.SSLOptions(tls_ctx, BROKER_HOST)
    )
    conn = pika.BlockingConnection(params)
    channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="fanout", durable=True)

    print("[AudioPublisher] Looking for MP3 files in audio_out...")
    
    try:
        while True:
            audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith('.mp3')]
            if not audio_files:
                print("[AudioPublisher] No MP3 files found. Waiting...")
                time.sleep(5)
                continue

            target_audio = audio_files[0]
            audio_path = os.path.join(AUDIO_DIR, target_audio)
            print(f"[AudioPublisher] Started streaming {target_audio}...")

            with open(audio_path, "rb") as af:
                chunk_index = 0
                while True:
                    chunk = af.read(CHUNK_SIZE)
                    if not chunk:
                        break  # End of file
                    
                    payload_data = {
                        "node_id": NODE_ID,
                        "timestamp_ns": time.time_ns(),
                        "audio_b64": base64.b64encode(chunk).decode('utf-8'),
                        "audio_filename": target_audio,
                        "chunk_index": chunk_index
                    }
                    
                    payload_bytes = json.dumps(payload_data).encode()

                    # 1. ML-KEM-768 Encapsulation
                    with oqs.KeyEncapsulation("ML-KEM-768") as kem:
                        kem_ciphertext, shared_secret = kem.encap_secret(SERVER_KEM_PUB)

                    # 2. AES-256-GCM Encryption
                    aesgcm = AESGCM(shared_secret[:32])
                    nonce = os.urandom(12)
                    encrypted_payload = aesgcm.encrypt(nonce, payload_bytes, None)

                    # 3. ML-DSA-65 Signature
                    auth_data = kem_ciphertext + nonce + encrypted_payload
                    with oqs.Signature("ML-DSA-65", PRIV_SIG_KEY) as signer:
                        signature = signer.sign(auth_data)

                    # 4. Build and Publish Envelope
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
                    print(f"  [AudioPublisher] Sent chunk {chunk_index} ({len(chunk)} bytes)")
                    chunk_index += 1
                    
                    # Pace the streaming to roughly match audio playback speed
                    # (Assuming 128kbps mp3, 64KB is ~4 seconds of audio. Let's send every 2 seconds to buffer ahead safely)
                    time.sleep(2)
            
            print(f"[AudioPublisher] Finished streaming {target_audio}. Waiting before repeating...")
            time.sleep(10) # Loop or wait for new file

    except KeyboardInterrupt:
        print("\n[AudioPublisher] Stopping transmission...")
        conn.close()

if __name__ == "__main__":
    main()

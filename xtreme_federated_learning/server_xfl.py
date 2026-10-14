import ssl
import json
import time
import os
import pika
import oqs
import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import numpy as np

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:4000/api/xfl")

def push_xfl_round(payload):
    """Pushes XFL round metrics to the unified React dashboard."""
    try:
        requests.post(DASHBOARD_URL, json=payload, timeout=2)
    except Exception:
        pass  # Dashboard being down should never interrupt FL

# ── AMQP & PQC Config ──────────────────────────────────────────
BROKER_HOST   = os.getenv("BROKER_HOST", "127.0.0.1")
BROKER_PORT   = int(os.getenv("BROKER_PORT", "5671"))
AMQP_USER     = os.getenv("AMQP_USER", "pqc_user")
AMQP_PASSWORD = os.getenv("AMQP_PASSWORD", "pqc_password")
EXCHANGE_UPDATES = "fl_updates"
EXCHANGE_GLOBAL  = "fl_global"
MIN_CLIENTS_PER_ROUND = max(1, int(os.getenv("XFL_MIN_CLIENTS_PER_ROUND", "2")))

# Paths
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CERT_DIR      = os.path.join(os.path.dirname(BASE_DIR), "certs")
CA_CERT       = os.path.join(CERT_DIR, "ca_certificate.pem")
CLIENT_CERT   = os.path.join(CERT_DIR, "server_certificate.pem")
CLIENT_KEY    = os.path.join(CERT_DIR, "server_key.pem")
KEM_KEY_PATH  = os.path.join(CERT_DIR, "consumer_kem_priv.key")
SERVER_PUB    = os.path.join(CERT_DIR, "server_kem_pub.key")

def make_tls_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_verify_locations(CA_CERT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx

def serialize_weights(weights):
    return [np.asarray(w).tolist() for w in weights]

EXPECTED_WEIGHT_SHAPES = [(20, 16), (16,), (16, 8), (8,), (8, 16), (16,), (16, 20), (20,)]

def deserialize_weights(encoded):
    if not isinstance(encoded, list) or len(encoded) != len(EXPECTED_WEIGHT_SHAPES):
        raise ValueError("Invalid model weight list")
    result = []
    for item, shape in zip(encoded, EXPECTED_WEIGHT_SHAPES):
        array = np.asarray(item, dtype=np.float32)
        if array.shape != shape or not np.isfinite(array).all() or np.max(np.abs(array), initial=0) > 1e3:
            raise ValueError("Invalid model weight shape or values")
        result.append(array)
    return result

class FederatedServer:
    def __init__(self):
        self.channel = None
        self.client_weights = []
        self.client_stats = []  # Track per-client training stats
        self.round_clients = set()
        self.round_number = 1
        
        # Server ML-DSA-65 Signer
        self.server_signer = oqs.Signature("ML-DSA-65")
        self.PUB_SIG_KEY = self.server_signer.generate_keypair()
        self.PRIV_SIG_KEY = self.server_signer.export_secret_key()
        
        # Load Client's public KEM to encrypt global weights to them (if needed)
        # Note: In fanout, we encrypt with a shared public key, or the server's own kem.
        # For simplicity, we use the server_kem_pub that the clients already have.
        # Wait, the clients need to decap. They generate ciphertext from SERVER_KEM_PUB.
        # Actually, for the server to broadcast to all clients, it should just sign it, or
        # the clients can just use TLS for confidentiality from broker to client.
        # But we'll stick to the symmetric PQC pipeline:
        # Server generates a random kem_ciphertext for the broadcast, or we just rely on TLS.
        # For PQC fanout broadcast, server can use a pre-shared KEM or just TLS. 
        # We will use the standard PQC envelope (Server signs, clients verify).

        if os.path.exists(KEM_KEY_PATH):
            with open(KEM_KEY_PATH, "rb") as f:
                self.CONSUMER_KEM_PRIV = f.read()
        else:
            self.CONSUMER_KEM_PRIV = None
            
        with open(SERVER_PUB, "rb") as f:
            self.SERVER_KEM_PUB = f.read()

    def start(self):
        print("[FL Server] Connecting to RabbitMQ...")
        tls_ctx = make_tls_context()
        params = pika.ConnectionParameters(
            host=BROKER_HOST, port=BROKER_PORT, virtual_host="/",
            credentials=pika.PlainCredentials(AMQP_USER, AMQP_PASSWORD),
            ssl_options=pika.SSLOptions(tls_ctx, BROKER_HOST),
            heartbeat=120,
            blocked_connection_timeout=300,
            connection_attempts=5,
            retry_delay=5,
            socket_timeout=10,
        )
        conn = pika.BlockingConnection(params)
        self.channel = conn.channel()
        
        self.channel.exchange_declare(exchange=EXCHANGE_UPDATES, exchange_type="fanout", durable=True)
        self.channel.exchange_declare(exchange=EXCHANGE_GLOBAL, exchange_type="fanout", durable=True)
        self.channel.basic_qos(prefetch_count=1)
        
        result = self.channel.queue_declare(queue="", exclusive=True)
        self.channel.queue_bind(exchange=EXCHANGE_UPDATES, queue=result.method.queue)
        self.channel.basic_consume(queue=result.method.queue, on_message_callback=self.on_client_update)

        print(f"[FL Server] Waiting for FL updates from clients (Target: {MIN_CLIENTS_PER_ROUND} clients/round)...")
        self.channel.start_consuming()

    def on_client_update(self, ch, method, properties, body):
        try:
            if len(body) > 10_000_000:
                raise ValueError("Update exceeds size limit")
            envelope = json.loads(body)
            kem_cipher   = bytes.fromhex(envelope["kem_cipher"])
            nonce        = bytes.fromhex(envelope["nonce"])
            enc_payload  = bytes.fromhex(envelope["enc_payload"])
            signature    = bytes.fromhex(envelope["signature"])
            pub_sig_key  = bytes.fromhex(envelope["pub_sig_key"])
            auth_data = kem_cipher + nonce + enc_payload
            with oqs.Signature("ML-DSA-65") as verifier:
                if not verifier.verify(auth_data, signature, pub_sig_key):
                    raise ValueError("Invalid client signature")
        except Exception as e:
            print(f"[FL Server] Rejected malformed envelope: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        if not self.CONSUMER_KEM_PRIV:
            print(" ❌ Missing ML-KEM Private Key for decryption!")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        try:
            with oqs.KeyEncapsulation("ML-KEM-768", self.CONSUMER_KEM_PRIV) as kem:
                shared_secret = kem.decap_secret(kem_cipher)
        except Exception as e:
            print(f"[FL Server] KEM decapsulation failed: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        aesgcm = AESGCM(shared_secret[:32])
        try:
            decrypted_bytes = aesgcm.decrypt(nonce, enc_payload, None)
            data = json.loads(decrypted_bytes)
        except Exception as e:
            print(f" ❌ Decryption failed: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        try:
            cid = str(data["cid"])
            update_round = int(data["round"])
            if not cid or len(cid) > 128 or update_round != self.round_number:
                raise ValueError("Unexpected client identity or round")
            if cid in self.round_clients:
                print(f"[FL Server] Ignoring duplicate update from client {cid} in round {self.round_number}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            weights = deserialize_weights(data["weights"])
            for field in ("avg_loss", "threshold"):
                value = float(data.get(field, 0.0))
                if not np.isfinite(value) or value < 0 or value > 1e6:
                    raise ValueError(f"Invalid {field}")
            for field in ("gated_anomalies", "trained_samples"):
                value = int(data.get(field, 0))
                if value < 0 or value > 100_000:
                    raise ValueError(f"Invalid {field}")
            self.round_clients.add(cid)
        except Exception as e:
            print(f"[FL Server] Rejected model update: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
        self.client_weights.append(weights)
        
        # Collect training stats from the client payload
        self.client_stats.append({
            "cid": cid,
            "avg_loss": float(data.get("avg_loss", 0.0)),
            "threshold": float(data.get("threshold", 0.0)),
            "gated_anomalies": int(data.get("gated_anomalies", 0)),
            "trained_samples": int(data.get("trained_samples", 0)),
        })
        
        print(f"[FL Server] Received weights from Client {cid} for Round {self.round_number} ({len(self.client_weights)}/{MIN_CLIENTS_PER_ROUND}) | Loss: {float(data.get('avg_loss', 0.0)):.5f} | Gated: {int(data.get('gated_anomalies', 0))}")
        
        if len(self.round_clients) >= MIN_CLIENTS_PER_ROUND:
            self.aggregate_and_broadcast()
            
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def aggregate_and_broadcast(self):
        print(f"\n[FL Server] Aggregating weights for Round {self.round_number}...")
        
        # Robust Aggregation (Coordinate-wise Median) to mitigate poisoned tensors
        aggregated_weights = []
        for weights_list_tuple in zip(*self.client_weights):
            layer_median = np.median(np.array(weights_list_tuple), axis=0)
            aggregated_weights.append(layer_median)

        # ── Compute meaningful anomaly detection stats for dashboard ─
        avg_loss_global = float(np.mean([s["avg_loss"] for s in self.client_stats])) if self.client_stats else 0.0
        avg_threshold   = float(np.mean([s["threshold"] for s in self.client_stats])) if self.client_stats else 0.0
        total_gated     = int(sum(s["gated_anomalies"] for s in self.client_stats))
        total_trained   = int(sum(s["trained_samples"] for s in self.client_stats))
        num_clients     = len(self.client_stats)
        gating_rate     = round(total_gated / max(total_gated + total_trained, 1) * 100, 1)

        xfl_payload = {
            "round": self.round_number,
            "num_clients": num_clients,
            "avg_reconstruction_loss": avg_loss_global,
            "avg_dynamic_threshold": avg_threshold,
            "total_gated_anomalies": total_gated,
            "total_trained_samples": total_trained,
            "gating_rate_pct": gating_rate,
            "timestamp": time.time()
        }
        push_xfl_round(xfl_payload)
        # ─────────────────────────────────────────────────────────────

        self.client_weights = []  # Reset for next round
        self.client_stats = []    # Reset stats for next round
        self.round_clients.clear()
        completed_round = self.round_number
        self.round_number += 1
        
        weights_data = serialize_weights(aggregated_weights)
        payload = json.dumps({"round": completed_round, "weights": weights_data}).encode()

        # All enrolled XFL clients currently share this recipient KEM keypair.
        # This protects the fanout body from the broker; per-client keys would
        # be needed to isolate one client from another.
        if not self.CONSUMER_KEM_PRIV:
            raise RuntimeError("Missing XFL recipient ML-KEM private key")
        with oqs.KeyEncapsulation("ML-KEM-768") as kem:
            kem_cipher, shared_secret = kem.encap_secret(self.SERVER_KEM_PUB)

        # Derive the AES key from ML-KEM output.
        aes_key = shared_secret[:32]
        aesgcm = AESGCM(aes_key)
        nonce = os.urandom(12)
        encrypted_payload = aesgcm.encrypt(nonce, payload, None)

        auth_data = kem_cipher + nonce + encrypted_payload
        with oqs.Signature("ML-DSA-65", self.PRIV_SIG_KEY) as signer:
            signature = signer.sign(auth_data)

        envelope = json.dumps({
            "kem_cipher": kem_cipher.hex(),
            "nonce": nonce.hex(),
            "enc_payload": encrypted_payload.hex(),
            "signature": signature.hex(),
            "pub_sig_key": self.PUB_SIG_KEY.hex()
        }).encode()

        self.channel.basic_publish(
            exchange=EXCHANGE_GLOBAL,
            routing_key="",
            body=envelope,
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2)
        )
        print(f"[FL Server] Broadcasted global weights for Round {self.round_number-1} to all clients.")

if __name__ == "__main__":
    server = FederatedServer()
    server.start()

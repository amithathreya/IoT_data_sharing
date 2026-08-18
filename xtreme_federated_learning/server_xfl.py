import ssl
import json
import time
import os
import pika
import oqs
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import numpy as np
import pickle
import base64

# ── AMQP & PQC Config ──────────────────────────────────────────
BROKER_HOST   = "127.0.0.1"
BROKER_PORT   = 5671
AMQP_USER     = "pqc_user"
AMQP_PASSWORD = "pqc_password"
EXCHANGE_UPDATES = "fl_updates"
EXCHANGE_GLOBAL  = "fl_global"
MIN_CLIENTS_PER_ROUND = 1  # Adjust this based on how many clients you have

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
    ctx.load_cert_chain(CLIENT_CERT, CLIENT_KEY)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx

def serialize_weights(weights):
    return base64.b64encode(pickle.dumps(weights)).decode('utf-8')

def deserialize_weights(b64_str):
    return pickle.loads(base64.b64decode(b64_str))

class FederatedServer:
    def __init__(self):
        self.channel = None
        self.client_weights = []
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
            ssl_options=pika.SSLOptions(tls_ctx, BROKER_HOST)
        )
        conn = pika.BlockingConnection(params)
        self.channel = conn.channel()
        
        self.channel.exchange_declare(exchange=EXCHANGE_UPDATES, exchange_type="fanout", durable=True)
        self.channel.exchange_declare(exchange=EXCHANGE_GLOBAL, exchange_type="fanout", durable=True)
        
        result = self.channel.queue_declare(queue="", exclusive=True)
        self.channel.queue_bind(exchange=EXCHANGE_UPDATES, queue=result.method.queue)
        self.channel.basic_consume(queue=result.method.queue, on_message_callback=self.on_client_update)

        print(f"[FL Server] Waiting for FL updates from clients (Target: {MIN_CLIENTS_PER_ROUND} clients/round)...")
        self.channel.start_consuming()

    def on_client_update(self, ch, method, properties, body):
        envelope = json.loads(body)

        kem_cipher   = bytes.fromhex(envelope["kem_cipher"])
        nonce        = bytes.fromhex(envelope["nonce"])
        enc_payload  = bytes.fromhex(envelope["enc_payload"])
        signature    = bytes.fromhex(envelope["signature"])
        pub_sig_key  = bytes.fromhex(envelope["pub_sig_key"])

        auth_data = kem_cipher + nonce + enc_payload
        with oqs.Signature("ML-DSA-65") as verifier:
            if not verifier.verify(auth_data, signature, pub_sig_key):
                print(" ❌ INVALID SIGNATURE from Client!\n")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

        if not self.CONSUMER_KEM_PRIV:
            print(" ❌ Missing ML-KEM Private Key for decryption!")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        with oqs.KeyEncapsulation("ML-KEM-768", self.CONSUMER_KEM_PRIV) as kem:
            shared_secret = kem.decap_secret(kem_cipher)

        aesgcm = AESGCM(shared_secret[:32])
        try:
            decrypted_bytes = aesgcm.decrypt(nonce, enc_payload, None)
            data = json.loads(decrypted_bytes)
        except Exception as e:
            print(f" ❌ Decryption failed: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        cid = data["cid"]
        weights = deserialize_weights(data["weights"])
        self.client_weights.append(weights)
        
        print(f"[FL Server] Received weights from Client {cid} for Round {self.round_number} ({len(self.client_weights)}/{MIN_CLIENTS_PER_ROUND})")
        
        if len(self.client_weights) >= MIN_CLIENTS_PER_ROUND:
            self.aggregate_and_broadcast()
            
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def aggregate_and_broadcast(self):
        print(f"\n[FL Server] Aggregating weights for Round {self.round_number}...")
        
        # Simple FedAvg: mean of all weights
        aggregated_weights = []
        for weights_list_tuple in zip(*self.client_weights):
            layer_mean = np.mean(np.array(weights_list_tuple), axis=0)
            aggregated_weights.append(layer_mean)
            
        self.client_weights = [] # Reset for next round
        self.round_number += 1
        
        weights_data = serialize_weights(aggregated_weights)
        payload = json.dumps({"round": self.round_number, "weights": weights_data}).encode()

        # Encapsulate using Server's own KEM public key (Clients will decap with Server's private key)
        # Wait, the clients don't have the server's private key!
        # The correct PQC fanout approach: Clients have SERVER_PUB, Server has SERVER_PRIV.
        # The clients cannot decap if the server encap'd with SERVER_PUB.
        # So for the server to broadcast, it should just sign it and send it via TLS.
        # Since we must use the envelope structure, we'll dummy encrypt or use a fixed symmetric key.
        # Let's use a random symmetric key, but how do clients get it?
        # A true PQC broadcast requires the server to encrypt individually for each client, 
        # or the clients to already share a symmetric key. 
        # To maintain the PQC envelope pattern without individually encrypting:
        # We will use the server's KEM public key to encapsulate, but since clients don't have the private key,
        # we will use the existing Consumer KEM private key that the clients already load!
        # Wait, in client_xfl.py: self.CONSUMER_KEM_PRIV is loaded by the clients.
        # The server will encapsulate using the Consumer's public key if it has it, but it doesn't.
        # Actually, let's just use the server's KEM Private key to encapsulate? No, KEM encapsulates with public key.
        # Let's bypass PQC encryption for the broadcast (TLS is enough) and just sign it with PQC signature.
        
        # Encrypt with a random AES key, and send the AES key in plaintext (since TLS protects the link)
        # OR just send plaintext over TLS.
        # Let's keep the envelope structure but use a dummy kem_cipher and send the AES key.
        aes_key = os.urandom(32)
        aesgcm = AESGCM(aes_key)
        nonce = os.urandom(12)
        encrypted_payload = aesgcm.encrypt(nonce, payload, None)
        
        # We will package the aes_key in the kem_cipher field (not secure against quantum eavesdropper on the AMQP broker itself, 
        # but TLS 1.3 provides the actual transport security here).
        dummy_kem_cipher = aes_key
        
        auth_data = dummy_kem_cipher + nonce + encrypted_payload
        with oqs.Signature("ML-DSA-65", self.PRIV_SIG_KEY) as signer:
            signature = signer.sign(auth_data)

        envelope = json.dumps({
            "kem_cipher": dummy_kem_cipher.hex(), # Using this field to pass the AES key
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

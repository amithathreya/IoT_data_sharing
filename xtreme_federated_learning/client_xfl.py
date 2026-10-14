import ssl
import json
import time
import os
import pika
import oqs
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import tensorflow as tf
import numpy as np
import pandas as pd
import psutil
import threading
import collections

# Reduce TensorFlow CPU pressure on Raspberry Pi by default.
TF_INTRA_OP_THREADS = int(os.getenv("TF_INTRA_OP_THREADS", "1"))
TF_INTER_OP_THREADS = int(os.getenv("TF_INTER_OP_THREADS", "1"))
try:
    tf.config.threading.set_intra_op_parallelism_threads(TF_INTRA_OP_THREADS)
    tf.config.threading.set_inter_op_parallelism_threads(TF_INTER_OP_THREADS)
except RuntimeError:
    # Safe fallback when TF runtime already initialized by environment bootstrap.
    pass

# ── Anomaly Detection Model ────────────────────────────────────
def get_model(input_shape=(20,)):
    model = tf.keras.models.Sequential([
        tf.keras.layers.Dense(16, activation="relu", input_shape=input_shape, name="enc_1"),
        tf.keras.layers.Dense(8, activation="relu", name="enc_2"),
        tf.keras.layers.Dense(16, activation="relu", name="dec_1"),
        tf.keras.layers.Dense(input_shape[0], name="output")
    ])
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return model

class NetworkMonitor:
    """
    Runs in a daemon background thread and continuously samples network I/O
    every 2.5 seconds into a rolling buffer. This means an attack launched at
    ANY point will be captured automatically in the next FL training round.
    """
    def __init__(self, window_size=30, interval=2.5):
        self.interval = interval
        # Each sample is a (scaled_sent, scaled_recv) pair. We keep the last
        # window_size * 2 values so we always have enough for training sequences.
        self.buffer = collections.deque(maxlen=window_size * 2)
        self.lock = threading.Lock()
        self.latest_window = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()
        print("[NetworkMonitor] Background I/O sampling started (2.5s interval). Attack can begin at any time.")

    def _run(self):
        prev_io = psutil.net_io_counters()
        while True:
            time.sleep(self.interval)
            curr_io = psutil.net_io_counters()
            bytes_sent = curr_io.bytes_sent - prev_io.bytes_sent
            bytes_recv = curr_io.bytes_recv - prev_io.bytes_recv
            prev_io = curr_io
            scaled_sent = np.log1p(bytes_sent) / 10.0
            scaled_recv = np.log1p(bytes_recv) / 10.0
            with self.lock:
                self.buffer.extend([scaled_sent, scaled_recv])
                if len(self.buffer) >= 20:
                    self.latest_window = np.asarray(list(self.buffer)[-20:], dtype=np.float32)

    def get_training_data(self, num_samples=20):
        """
        Build a training dataset from the current rolling buffer.
        Returns (X_train, y_train) ready for the Loss-Gating loop.
        """
        with self.lock:
            buf = list(self.buffer)  # snapshot
        X_train, y_train = [], []

        # Slide a window of 20 values across the buffer to create sequences
        for i in range(len(buf) - 19):
            X_train.append(buf[i:i + 20])
            y_train.append(0)  # Class 0 = Normal (real data)

        # Keep only the most recent num_samples real samples.
        # If we have fewer, just use what we have — never pad with zeros
        # as zero-vectors corrupt the threshold_history with 0.0 scores.
        X_train = X_train[-num_samples:]
        y_train = y_train[-num_samples:]

        # Inject synthetic anomalies so the model always knows what a spike looks like
        num_anomalies = max(1, len(X_train) // 2)
        for _ in range(num_anomalies):
            anomaly_sequence = []
            normal_sent = float(np.random.uniform(4.0, 6.0)) / 10.0
            normal_recv = float(np.random.uniform(4.0, 6.0)) / 10.0
            spike_length = np.random.randint(1, 11)
            spike_sent = float(np.random.uniform(8.0, 12.0)) / 10.0
            spike_recv = float(np.random.uniform(8.0, 12.0)) / 10.0
            for i in range(10):
                if i >= (10 - spike_length):
                    rand_sent = spike_sent + float(np.random.uniform(-0.5, 0.5)) / 10.0
                    rand_recv = spike_recv + float(np.random.uniform(-0.5, 0.5)) / 10.0
                else:
                    rand_sent = normal_sent + float(np.random.uniform(-0.2, 0.2)) / 10.0
                    rand_recv = normal_recv + float(np.random.uniform(-0.2, 0.2)) / 10.0
                anomaly_sequence.extend([rand_sent, rand_recv])
            X_train.append(anomaly_sequence)
            y_train.append(int(np.random.randint(1, 9)))

        if len(X_train) == 0:
            print("[NetworkMonitor] Buffer not warm yet, waiting for more samples...")
        else:
            print(f"[NetworkMonitor] Snapshot: {len(X_train) - num_anomalies} real + {num_anomalies} synthetic anomaly samples.")

        return np.array(X_train), np.array(y_train)

# ── AMQP & PQC Config ──────────────────────────────────────────
BROKER_HOST   = os.getenv("BROKER_HOST", "127.0.0.1")
BROKER_PORT   = int(os.getenv("BROKER_PORT", "5671"))
AMQP_USER     = os.getenv("AMQP_USER", "pqc_user")
AMQP_PASSWORD = os.getenv("AMQP_PASSWORD", "pqc_password")
EXCHANGE_UPDATES = "fl_updates"
EXCHANGE_GLOBAL  = "fl_global"

# Paths
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CERT_DIR      = os.path.join(os.path.dirname(BASE_DIR), "certs")
CA_CERT       = os.path.join(CERT_DIR, "ca_certificate.pem")
CLIENT_CERT   = os.path.join(CERT_DIR, "server_certificate.pem")
CLIENT_KEY    = os.path.join(CERT_DIR, "server_key.pem")
SERVER_PUB    = os.path.join(CERT_DIR, "server_kem_pub.key")
KEM_KEY_PATH  = os.path.join(CERT_DIR, "consumer_kem_priv.key")

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

def deserialize_weights(encoded, reference_weights):
    if not isinstance(encoded, list) or len(encoded) != len(reference_weights):
        raise ValueError("Invalid model weight list")
    result = []
    for item, reference in zip(encoded, reference_weights):
        array = np.asarray(item, dtype=np.float32)
        if array.shape != reference.shape or not np.isfinite(array).all() or np.max(np.abs(array), initial=0) > 1e3:
            raise ValueError("Invalid model weight shape or values")
        result.append(array)
    return result

class FederatedClient:
    def __init__(self, cid):
        self.cid = cid
        self.model = get_model()
        self.threshold_history = collections.deque(maxlen=100)
        self.k = 3.0
        self.model_lock = threading.RLock()
        self.current_round = 1
        self.initial_update_scheduled = False
        self.channel = None
        self.state_lock = threading.Lock()
        self.pending_global_weights = None
        self.is_training = False

        if os.name == 'posix' and os.path.exists('/dev/shm'):
            self.weights_out = "/dev/shm/local_model.weights.h5"
            self.threshold_out = "/dev/shm/local_model_threshold.json"
        else:
            self.weights_out = os.path.join(BASE_DIR, "local_model.weights.h5")
            self.threshold_out = os.path.join(BASE_DIR, "local_model_threshold.json")

        # Start the continuous background network monitor immediately.
        # This captures traffic at ALL times, so an attack at any moment
        # will be reflected in the next training round automatically.
        self.network_monitor = NetworkMonitor(window_size=30, interval=2.5)
        self.network_monitor.start()
        threading.Thread(target=self._score_live_traffic, daemon=True).start()
        threading.Thread(target=self._wait_for_initial_data, daemon=True).start()

        # Publisher ML-DSA-65 Signer
        self.publisher_signer = oqs.Signature("ML-DSA-65")
        self.PUB_SIG_KEY = self.publisher_signer.generate_keypair()
        self.PRIV_SIG_KEY = self.publisher_signer.export_secret_key()
        
        with open(SERVER_PUB, "rb") as f:
            self.SERVER_KEM_PUB = f.read()

        if os.path.exists(KEM_KEY_PATH):
            with open(KEM_KEY_PATH, "rb") as f:
                self.CONSUMER_KEM_PRIV = f.read()
        else:
            self.CONSUMER_KEM_PRIV = None

    def _safe_save_weights(self, path, retries=5, base_sleep=0.2):
        tmp_path = path.replace(".weights.h5", ".tmp.weights.h5")
        for attempt in range(1, retries + 1):
            try:
                self.model.save_weights(tmp_path)
                os.replace(tmp_path, path)
                return True
            except BlockingIOError:
                if attempt == retries:
                    break
                wait_s = base_sleep * attempt
                print(f"[Client {self.cid}] Weights file busy; retrying in {wait_s:.2f}s ({attempt}/{retries})...")
                time.sleep(wait_s)
            except Exception:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                raise

        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return False

    def _schedule_training(self, global_weights=None):
        should_spawn = False
        with self.state_lock:
            if global_weights is not None:
                # Keep only the latest global state to avoid backlog on slow devices.
                self.pending_global_weights = global_weights
            if not self.is_training:
                self.is_training = True
                should_spawn = True

        if should_spawn:
            threading.Thread(target=self._training_worker, daemon=True).start()

    def _training_worker(self):
        while True:
            with self.state_lock:
                next_weights = self.pending_global_weights
                self.pending_global_weights = None

            if next_weights is not None:
                with self.model_lock:
                    self.model.set_weights(next_weights)
                try:
                    with self.model_lock:
                        self._safe_save_weights(self.weights_out)
                except Exception as e:
                    print(f"[Client {self.cid}] Could not persist received global weights: {e}")

            self.train_and_send()

            with self.state_lock:
                if self.pending_global_weights is None:
                    self.is_training = False
                    return
                print(f"[Client {self.cid}] New global update arrived during training. Starting next round immediately.")

    def start(self):
        print(f"[Client {self.cid}] Connecting to RabbitMQ...")
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
        self.channel.queue_bind(exchange=EXCHANGE_GLOBAL, queue=result.method.queue)
        self.channel.basic_consume(queue=result.method.queue, on_message_callback=self.on_global_weights)

        print(f"[Client {self.cid}] Waiting for global FL updates...")
        self.channel.start_consuming()

    def _eval_step(self, x_batch):
        with self.model_lock:
            return self.model(x_batch, training=False)

    def _train_step(self, x_batch):
        with self.model_lock:
            with tf.GradientTape() as tape:
                reconstruction = self.model(x_batch, training=True)
                loss_value = tf.reduce_mean(tf.square(x_batch - reconstruction))
            grads = tape.gradient(loss_value, self.model.trainable_weights)
            self.model.optimizer.apply_gradients(zip(grads, self.model.trainable_weights))
            return loss_value

    def _wait_for_initial_data(self):
        while True:
            with self.network_monitor.lock:
                ready = len(self.network_monitor.buffer) >= 20 and self.channel is not None
            if ready:
                if not self.initial_update_scheduled:
                    self.initial_update_scheduled = True
                    self._schedule_training()
                return
            time.sleep(1.0)

    def _score_live_traffic(self):
        last_window = None
        while True:
            with self.network_monitor.lock:
                window = None if self.network_monitor.latest_window is None else self.network_monitor.latest_window.copy()
            if window is not None and (last_window is None or not np.array_equal(last_window, window)):
                batch = tf.convert_to_tensor(window.reshape(1, -1), dtype=tf.float32)
                reconstruction = self._eval_step(batch)
                score = float(tf.reduce_mean(tf.square(batch - reconstruction)))
                threshold = max(float(np.mean(self.threshold_history) + self.k * np.std(self.threshold_history)), 0.05) if len(self.threshold_history) > 10 else 1.0
                if score >= threshold:
                    print(f"[Client {self.cid}] LIVE ANOMALY score={score:.5f}, threshold={threshold:.5f}")
                last_window = window
            time.sleep(0.5)

    def train_and_send(self):
        print(f"[Client {self.cid}] Fetching latest network data from live monitor for training...")
        x_train, y_train = self.network_monitor.get_training_data(num_samples=20)

        if len(x_train) == 0:
            print(f"[Client {self.cid}] Not enough data yet. Waiting for next round...")
            return

        print(f"[Client {self.cid}] Starting local training on live data with Loss-Gating...")
        
        total_loss = 0.0
        trained_samples = 0
        gated_anomalies = 0
        
        for idx in range(len(x_train)):
            x_batch = x_train[idx:idx+1]
            x_batch_tf = tf.convert_to_tensor(x_batch, dtype=tf.float32)
            
            # 1. Forward pass in eval mode to get reconstruction error
            reconstruction = self._eval_step(x_batch_tf)
            anomaly_score = float(tf.reduce_mean(tf.square(x_batch_tf - reconstruction)))
            
            # Calculate dynamic threshold with a hard floor to prevent collapse to 0.
            # MIN_THRESHOLD ensures even a model with near-zero reconstruction loss
            # never flags every sample as anomalous.
            MIN_THRESHOLD = 0.05
            if len(self.threshold_history) > 10:
                mu_loss = np.mean(self.threshold_history)
                sigma_loss = np.std(self.threshold_history)
                dynamic_threshold = max(mu_loss + (self.k * sigma_loss), MIN_THRESHOLD)
            else:
                dynamic_threshold = 1.0  # Permissive warmup: let samples through to build history
                
            # 2. Loss-Gating
            is_anomaly = anomaly_score >= dynamic_threshold
            
            if is_anomaly:
                gated_anomalies += 1
                print(f" [!] Sample {idx} - ANOMALY DETECTED (Score: {anomaly_score:.4f} >= Threshold: {dynamic_threshold:.4f}). Freezing backprop.")
            else:
                self.threshold_history.append(anomaly_score)
                total_loss += anomaly_score
                trained_samples += 1
                # Switch to train mode and backpropagate
                self._train_step(x_batch_tf)
        
        avg_loss = total_loss / trained_samples if trained_samples > 0 else 0.0
        
        current_threshold = 1.0
        try:
            with self.model_lock:
                if not self._safe_save_weights(self.weights_out):
                    raise BlockingIOError("local_model.weights.h5 remained locked after retries")
            
            if len(self.threshold_history) > 10:
                mu_loss = np.mean(self.threshold_history)
                sigma_loss = np.std(self.threshold_history)
                current_threshold = max(float(mu_loss + (self.k * sigma_loss)), 0.05)
                
            with open(self.threshold_out, "w") as f:
                json.dump({"dynamic_threshold": current_threshold}, f)
                
            print(f"[Client {self.cid}] Saved updated weights & threshold ({current_threshold:.5f}) to {self.weights_out} for publisher.")
        except Exception as e:
            print(f"[Client] Could not save weights or threshold: {e}")

        with self.model_lock:
            weights_data = serialize_weights(self.model.get_weights())
        payload = json.dumps({
            "cid": self.cid,
            "round": self.current_round,
            "weights": weights_data,
            "avg_loss": avg_loss,
            "threshold": current_threshold,
            "gated_anomalies": gated_anomalies,
            "trained_samples": trained_samples
        }).encode()

        with oqs.KeyEncapsulation("ML-KEM-768") as kem:
            kem_ciphertext, shared_secret = kem.encap_secret(self.SERVER_KEM_PUB)

        aesgcm = AESGCM(shared_secret[:32])
        nonce = os.urandom(12)
        encrypted_payload = aesgcm.encrypt(nonce, payload, None)

        auth_data = kem_ciphertext + nonce + encrypted_payload
        with oqs.Signature("ML-DSA-65", self.PRIV_SIG_KEY) as signer:
            signature = signer.sign(auth_data)

        envelope = json.dumps({
            "kem_cipher": kem_ciphertext.hex(),
            "nonce": nonce.hex(),
            "enc_payload": encrypted_payload.hex(),
            "signature": signature.hex(),
            "pub_sig_key": self.PUB_SIG_KEY.hex()
        }).encode()

        def publish_message():
            if not self.channel or self.channel.is_closed:
                print(f"[Client {self.cid}] Channel closed before publish; skipping update push.")
                return
            self.channel.basic_publish(
                exchange=EXCHANGE_UPDATES,
                routing_key="",
                body=envelope,
                properties=pika.BasicProperties(content_type="application/json", delivery_mode=2)
            )
            print(f"[Client {self.cid}] Sent encrypted weights to server.")
            
        self.channel.connection.add_callback_threadsafe(publish_message)

    def on_global_weights(self, ch, method, properties, body):
        print(f"\n[Client {self.cid}] Received new global weights!")
        if len(body) > 10_000_000:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f"[Client {self.cid}] Rejected oversized global model")
            return
        try:
            envelope = json.loads(body)

            kem_cipher   = bytes.fromhex(envelope["kem_cipher"])
            nonce        = bytes.fromhex(envelope["nonce"])
            enc_payload  = bytes.fromhex(envelope["enc_payload"])
            signature    = bytes.fromhex(envelope["signature"])
            pub_sig_key  = bytes.fromhex(envelope["pub_sig_key"])

            auth_data = kem_cipher + nonce + enc_payload
            with oqs.Signature("ML-DSA-65") as verifier:
                if not verifier.verify(auth_data, signature, pub_sig_key):
                    raise ValueError("Invalid server signature")
        except Exception as e:
            print(f"[Client {self.cid}] Rejected malformed global update: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        try:
            if not self.CONSUMER_KEM_PRIV:
                raise ValueError("Missing client ML-KEM private key")
            with oqs.KeyEncapsulation("ML-KEM-768", self.CONSUMER_KEM_PRIV) as kem:
                shared_secret = kem.decap_secret(kem_cipher)
            aesgcm = AESGCM(shared_secret[:32])
            decrypted_bytes = aesgcm.decrypt(nonce, enc_payload, None)
            data = json.loads(decrypted_bytes)
        except Exception as e:
            print(f" ❌ Decryption failed: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        try:
            received_round = int(data.get("round", -1))
            if received_round < self.current_round:
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            global_weights = deserialize_weights(data["weights"], self.model.get_weights())
        except Exception as e:
            print(f"[Client {self.cid}] Rejected invalid global model: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
        self.current_round = received_round + 1
        ch.basic_ack(delivery_tag=method.delivery_tag)
        self._schedule_training(global_weights)

if __name__ == "__main__":
    try:
        cid_input = input("Enter your client rank (0 for Client 1, 1 for Client 2, etc.) [Default 0]: ")
        cid = int(cid_input) if cid_input.strip() else 0
    except:
        cid = 0
    client = FederatedClient(cid)
    client.start()

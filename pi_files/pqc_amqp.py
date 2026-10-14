"""Shared TLS 1.3 + ML-KEM/AES-GCM + ML-DSA RabbitMQ transport helpers."""

import json
import os
import ssl
from pathlib import Path

try:
    import oqs
    import pika
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError as exc:
    raise RuntimeError("Install pika, oqs (liboqs-python), and cryptography for PQC AMQP transport") from exc

BROKER_HOST = os.getenv("BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(os.getenv("BROKER_PORT", "5671"))
AMQP_USER = os.getenv("AMQP_USER", "pqc_user")
AMQP_PASSWORD = os.getenv("AMQP_PASSWORD", "pqc_password")
UPDATE_EXCHANGE = "xgb_fl_updates"
GLOBAL_EXCHANGE = "xgb_fl_global"
MAX_MESSAGE_BYTES = 25 * 1024 * 1024


def _cert_dir() -> Path:
    here = Path(__file__).resolve().parent
    candidates = (here / "certs", here.parent / "certs")
    return next((path for path in candidates if path.is_dir()), candidates[-1])


def load_kem_keys():
    cert_dir = _cert_dir()
    public_path = cert_dir / "server_kem_pub.key"
    private_path = cert_dir / "consumer_kem_priv.key"
    if not public_path.is_file() or not private_path.is_file():
        raise FileNotFoundError(
            f"Missing ML-KEM keys in {cert_dir}; provision server_kem_pub.key and consumer_kem_priv.key"
        )
    return public_path.read_bytes(), private_path.read_bytes()


def load_kem_public_key():
    public_path = _cert_dir() / "server_kem_pub.key"
    if not public_path.is_file():
        raise FileNotFoundError(f"Missing ML-KEM public key: {public_path}")
    return public_path.read_bytes()


def make_tls_context():
    cert_dir = _cert_dir()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_verify_locations(str(cert_dir / "ca_certificate.pem"))
    ctx.load_cert_chain(str(cert_dir / "server_certificate.pem"), str(cert_dir / "server_key.pem"))
    ctx.check_hostname = False  # matches the existing RabbitMQ clients
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def connect_broker():
    params = pika.ConnectionParameters(
        host=BROKER_HOST,
        port=BROKER_PORT,
        virtual_host="/",
        credentials=pika.PlainCredentials(AMQP_USER, AMQP_PASSWORD),
        ssl_options=pika.SSLOptions(make_tls_context(), BROKER_HOST),
        heartbeat=120,
        blocked_connection_timeout=300,
        connection_attempts=5,
        retry_delay=5,
        socket_timeout=10,
    )
    return pika.BlockingConnection(params)


def seal_message(payload: bytes, recipient_kem_public: bytes, signer, signer_public_key: bytes) -> bytes:
    """Create the same hex JSON envelope used by the sensor/XFL publishers."""
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ValueError(f"PQC message exceeds {MAX_MESSAGE_BYTES} byte limit")
    with oqs.KeyEncapsulation("ML-KEM-768") as kem:
        kem_cipher, shared_secret = kem.encap_secret(recipient_kem_public)
    nonce = os.urandom(12)
    encrypted = AESGCM(shared_secret[:32]).encrypt(nonce, payload, None)
    signed_bytes = kem_cipher + nonce + encrypted
    signature = signer.sign(signed_bytes)
    envelope = {
        "kem_cipher": kem_cipher.hex(),
        "nonce": nonce.hex(),
        "enc_payload": encrypted.hex(),
        "signature": signature.hex(),
        "pub_sig_key": signer_public_key.hex(),
    }
    return json.dumps(envelope, separators=(",", ":")).encode("utf-8")


def open_message(body: bytes, recipient_kem_private: bytes) -> bytes:
    if len(body) > MAX_MESSAGE_BYTES * 2:
        raise ValueError("PQC envelope exceeds configured size limit")
    envelope = json.loads(body)
    kem_cipher = bytes.fromhex(envelope["kem_cipher"])
    nonce = bytes.fromhex(envelope["nonce"])
    encrypted = bytes.fromhex(envelope["enc_payload"])
    signature = bytes.fromhex(envelope["signature"])
    public_key = bytes.fromhex(envelope["pub_sig_key"])
    signed_bytes = kem_cipher + nonce + encrypted
    with oqs.Signature("ML-DSA-65") as verifier:
        if not verifier.verify(signed_bytes, signature, public_key):
            raise ValueError("Invalid ML-DSA-65 signature")
    with oqs.KeyEncapsulation("ML-KEM-768", recipient_kem_private) as kem:
        shared_secret = kem.decap_secret(kem_cipher)
    return AESGCM(shared_secret[:32]).decrypt(nonce, encrypted, None)


def seal_broadcast_message(payload: bytes, signer, signer_public_key: bytes) -> bytes:
    """Match existing XFL fanout: signed envelope; TLS 1.3 protects the AES key."""
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ValueError(f"PQC message exceeds {MAX_MESSAGE_BYTES} byte limit")
    aes_key = os.urandom(32)
    nonce = os.urandom(12)
    encrypted = AESGCM(aes_key).encrypt(nonce, payload, None)
    signed_bytes = aes_key + nonce + encrypted
    envelope = {
        "kem_cipher": aes_key.hex(),
        "nonce": nonce.hex(),
        "enc_payload": encrypted.hex(),
        "signature": signer.sign(signed_bytes).hex(),
        "pub_sig_key": signer_public_key.hex(),
    }
    return json.dumps(envelope, separators=(",", ":")).encode("utf-8")


def open_broadcast_message(body: bytes) -> bytes:
    """Open an existing XFL-style signed fanout message received over AMQPS."""
    if len(body) > MAX_MESSAGE_BYTES * 2:
        raise ValueError("PQC envelope exceeds configured size limit")
    envelope = json.loads(body)
    aes_key = bytes.fromhex(envelope["kem_cipher"])
    nonce = bytes.fromhex(envelope["nonce"])
    encrypted = bytes.fromhex(envelope["enc_payload"])
    signature = bytes.fromhex(envelope["signature"])
    public_key = bytes.fromhex(envelope["pub_sig_key"])
    signed_bytes = aes_key + nonce + encrypted
    with oqs.Signature("ML-DSA-65") as verifier:
        if not verifier.verify(signed_bytes, signature, public_key):
            raise ValueError("Invalid ML-DSA-65 signature")
    return AESGCM(aes_key[:32]).decrypt(nonce, encrypted, None)


def new_signer():
    signer = oqs.Signature("ML-DSA-65")
    public_key = signer.generate_keypair()
    return signer, public_key

"""
pqc_bench.py — PQC / Cryptographic Layer Benchmarks
=====================================================
Research paper Section: "PQC Cryptographic Layer Evaluation"

Measurements:
  1. TLS Handshake Time  : TLS 1.3 mutual authentication vs
                           classical TLS 1.2 ECDHE (not a PQC-TLS measurement)
                           → wraps raw socket.connect() + ssl.wrap_socket()
                           → 50-100 trials each, mean/median/stddev/p95

  2. ML-DSA-65 Sign/Verify Latency
                           → times oqs.Signature.sign() and .verify() directly
                           → 100 trials each, results in microseconds

  3. Signature & Ciphertext Size Overhead
                           → reports byte lengths of all PQC and classical
                             artefacts (no network needed, purely static)

Usage:
  # Full benchmark (requires RabbitMQ on port 5671 for TLS handshake):
  python benchmarks/pqc_bench.py

  # Skip TLS handshake (offline-only crypto benchmarks):
  python benchmarks/pqc_bench.py --skip-tls

Run from the project root: d:/major_project_server/
"""

import argparse
import os
import socket
import ssl
import sys
import time
from pathlib import Path

# ── path bootstrap so bench_utils is importable from project root ──
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchmarks.bench_utils import banner, print_table, save_csv, save_metadata, stats

try:
    import oqs
except ImportError:
    print("[ERROR] liboqs-python not installed. Run: pip install liboqs")
    sys.exit(1)

try:
    import numpy as np
except ImportError:
    print("[ERROR] numpy not installed. Run: pip install numpy")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
#  Configuration — mirrors server.py / publisher.py settings
# ─────────────────────────────────────────────────────────────────────────────
BROKER_HOST = "127.0.0.1"
BROKER_PORT = 5671

BASE_DIR = Path(__file__).resolve().parent.parent
CERT_DIR = BASE_DIR / "certs"
CA_CERT     = str(CERT_DIR / "ca_certificate.pem")
CLIENT_CERT = str(CERT_DIR / "server_certificate.pem")
CLIENT_KEY  = str(CERT_DIR / "server_key.pem")

TLS_TRIALS  = 50      # Number of TLS handshake trials per mode
CRYPTO_TRIALS = 100   # Number of sign/verify trials


# ─────────────────────────────────────────────────────────────────────────────
#  Section 1 — TLS Handshake Timing
# ─────────────────────────────────────────────────────────────────────────────

def _make_tls13_ctx() -> ssl.SSLContext:
    """TLS 1.3 mutual-auth context — matches publisher.py / server.py exactly."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_verify_locations(CA_CERT)
    ctx.load_cert_chain(CLIENT_CERT, CLIENT_KEY)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def _make_tls12_ecdhe_ctx() -> ssl.SSLContext:
    """
    TLS 1.2 context restricted to ECDHE cipher suites — classical baseline.
    We deliberately cap at TLS 1.2 so the handshake cannot upgrade to TLS 1.3
    and uses ECDHE-RSA key exchange instead of any KEM.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_verify_locations(CA_CERT)
    ctx.load_cert_chain(CLIENT_CERT, CLIENT_KEY)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    # Restrict to ECDHE cipher suites only for a clean classical baseline
    ctx.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20")
    return ctx


def _timed_handshake(ctx: ssl.SSLContext) -> float:
    """
    Open a raw TCP connection and perform a TLS handshake.
    Returns the handshake wall-clock time in milliseconds.
    The connection is closed immediately after do_handshake() returns.
    """
    raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw.settimeout(10)
    try:
        t0 = time.perf_counter()
        raw.connect((BROKER_HOST, BROKER_PORT))
        tls_sock = ctx.wrap_socket(raw, server_hostname=BROKER_HOST)
        tls_sock.do_handshake()
        t1 = time.perf_counter()
        tls_sock.close()
        return (t1 - t0) * 1000.0  # ms
    except Exception as e:
        raw.close()
        raise e


def bench_tls_handshake(n: int = TLS_TRIALS):
    banner(f"Section 1 — TLS Handshake Time ({n} trials each)")

    # Check cert files exist before connecting
    for path in [CA_CERT, CLIENT_CERT, CLIENT_KEY]:
        if not os.path.exists(path):
            print(f"[WARN] Certificate not found: {path}")
            print("       TLS handshake benchmarks require RabbitMQ + valid certs.")
            print("       Run with --skip-tls to measure crypto-only benchmarks.\n")
            return None, None

    print(f"Connecting to {BROKER_HOST}:{BROKER_PORT} for {n} trials each...")
    print("  Mode A : TLS 1.3 mutual TLS (classical transport; no ML-KEM negotiation)")
    print("  Mode B : TLS 1.2 (ECDHE path — classical baseline)\n")

    tls13_ctx = _make_tls13_ctx()
    tls12_ctx = _make_tls12_ecdhe_ctx()

    # Warm-up: 3 handshakes each to prime TCP stack caches
    for _ in range(3):
        try:
            _timed_handshake(tls13_ctx)
            _timed_handshake(tls12_ctx)
        except Exception:
            pass

    tls13_times, tls12_times = [], []
    for i in range(n):
        try:
            tls13_times.append(_timed_handshake(tls13_ctx))
        except Exception as e:
            print(f"  [WARN] TLS 1.3 trial {i} failed: {e}")
        try:
            tls12_times.append(_timed_handshake(tls12_ctx))
        except Exception as e:
            print(f"  [WARN] TLS 1.2 trial {i} failed: {e}")

        if (i + 1) % 10 == 0:
            print(f"  Progress: {i+1}/{n} trials completed...")

    if not tls13_times or not tls12_times:
        print("[ERROR] No successful handshake trials recorded. Is RabbitMQ running?")
        return None, None

    s13 = stats(tls13_times)
    s12 = stats(tls12_times)

    print_table(
        headers=["Mode", "N", "Mean (ms)", "Median (ms)", "StdDev (ms)", "p95 (ms)", "Min (ms)", "Max (ms)"],
        rows=[
            ["TLS 1.3 mutual TLS (classical transport)",
             s13["n"], f"{s13['mean']:.2f}", f"{s13['median']:.2f}",
             f"{s13['stddev']:.2f}", f"{s13['p95']:.2f}",
             f"{s13['min']:.2f}", f"{s13['max']:.2f}"],
            ["TLS 1.2 (Classical ECDHE)",
             s12["n"], f"{s12['mean']:.2f}", f"{s12['median']:.2f}",
             f"{s12['stddev']:.2f}", f"{s12['p95']:.2f}",
             f"{s12['min']:.2f}", f"{s12['max']:.2f}"],
        ],
        title="TLS Handshake Latency Results",
    )

    overhead_pct = ((s13["mean"] - s12["mean"]) / s12["mean"]) * 100
    print(f"  Overhead of TLS 1.3 vs TLS 1.2 ECDHE: {overhead_pct:+.1f}%")
    print("  (ML-KEM is applied by the application after AMQP connection setup, so it")
    print("   does not contribute to this TLS handshake measurement.)\n")

    save_csv(
        "tls_handshake_results.csv",
        ["mode", "n", "mean_ms", "median_ms", "stddev_ms", "p95_ms", "min_ms", "max_ms", "raw_samples_json"],
        [
            ["TLS 1.3 mutual TLS", s13["n"], f"{s13['mean']:.4f}",
             f"{s13['median']:.4f}", f"{s13['stddev']:.4f}", f"{s13['p95']:.4f}",
             f"{s13['min']:.4f}", f"{s13['max']:.4f}", str(tls13_times)],
            ["TLS 1.2 (ECDHE classical)", s12["n"], f"{s12['mean']:.4f}",
             f"{s12['median']:.4f}", f"{s12['stddev']:.4f}", f"{s12['p95']:.4f}",
             f"{s12['min']:.4f}", f"{s12['max']:.4f}", str(tls12_times)],
        ],
    )
    return s13, s12


# ─────────────────────────────────────────────────────────────────────────────
#  Section 2 — ML-DSA-65 Sign / Verify Latency
# ─────────────────────────────────────────────────────────────────────────────

def bench_sign_verify(n: int = CRYPTO_TRIALS):
    banner(f"Section 2 — ML-DSA-65 Sign / Verify Latency ({n} trials each)")

    # Generate a keypair once — matches publisher.py pattern
    signer = oqs.Signature("ML-DSA-65")
    pub_key = signer.generate_keypair()
    priv_key = signer.export_secret_key()

    # Use a realistic auth_data blob (kem_cipher + nonce + enc_payload)
    # Sizes from publisher.py: ML-KEM-768 ciphertext=1088 B, nonce=12 B, payload~300 B
    dummy_auth_data = os.urandom(1088 + 12 + 350)

    # ── Sign timing ──────────────────────────────────────────────────────────
    print(f"Running {n} ML-DSA-65 sign() trials...")
    sign_times_us = []
    signatures = []
    for _ in range(n):
        with oqs.Signature("ML-DSA-65", priv_key) as s:
            t0 = time.perf_counter()
            sig = s.sign(dummy_auth_data)
            t1 = time.perf_counter()
        sign_times_us.append((t1 - t0) * 1e6)
        signatures.append(sig)

    # ── Verify timing ─────────────────────────────────────────────────────────
    print(f"Running {n} ML-DSA-65 verify() trials...")
    verify_times_us = []
    for sig in signatures:
        with oqs.Signature("ML-DSA-65") as v:
            t0 = time.perf_counter()
            result = v.verify(dummy_auth_data, sig, pub_key)
            t1 = time.perf_counter()
        verify_times_us.append((t1 - t0) * 1e6)

    ss = stats(sign_times_us)
    sv = stats(verify_times_us)

    print_table(
        headers=["Operation", "N", "Mean (μs)", "Median (μs)", "StdDev (μs)", "p95 (μs)", "Min (μs)", "Max (μs)"],
        rows=[
            ["ML-DSA-65 sign()",
             ss["n"], f"{ss['mean']:.1f}", f"{ss['median']:.1f}",
             f"{ss['stddev']:.1f}", f"{ss['p95']:.1f}",
             f"{ss['min']:.1f}", f"{ss['max']:.1f}"],
            ["ML-DSA-65 verify()",
             sv["n"], f"{sv['mean']:.1f}", f"{sv['median']:.1f}",
             f"{sv['stddev']:.1f}", f"{sv['p95']:.1f}",
             f"{sv['min']:.1f}", f"{sv['max']:.1f}"],
        ],
        title="ML-DSA-65 Sign / Verify Latency (μs)",
    )

    save_csv(
        "sign_verify_latency.csv",
        ["operation", "n", "mean_us", "median_us", "stddev_us", "p95_us", "min_us", "max_us"],
        [
            ["ML-DSA-65 sign()", ss["n"], f"{ss['mean']:.2f}", f"{ss['median']:.2f}",
             f"{ss['stddev']:.2f}", f"{ss['p95']:.2f}", f"{ss['min']:.2f}", f"{ss['max']:.2f}"],
            ["ML-DSA-65 verify()", sv["n"], f"{sv['mean']:.2f}", f"{sv['median']:.2f}",
             f"{sv['stddev']:.2f}", f"{sv['p95']:.2f}", f"{sv['min']:.2f}", f"{sv['max']:.2f}"],
        ],
    )
    return ss, sv


# ─────────────────────────────────────────────────────────────────────────────
#  Section 3 — Signature & Ciphertext Size Overhead
# ─────────────────────────────────────────────────────────────────────────────

def bench_sizes():
    banner("Section 3 — Signature & Ciphertext Size Overhead")

    # ── ML-DSA-65 signature ──────────────────────────────────────────────────
    signer = oqs.Signature("ML-DSA-65")
    pub_key = signer.generate_keypair()
    priv_key = signer.export_secret_key()
    dummy_data = os.urandom(1088 + 12 + 350)
    with oqs.Signature("ML-DSA-65", priv_key) as s:
        mldsa_sig = s.sign(dummy_data)
    mldsa_sig_bytes   = len(mldsa_sig)
    mldsa_pubkey_bytes = len(pub_key)

    # ── ML-KEM-768 ciphertext & public key ───────────────────────────────────
    with oqs.KeyEncapsulation("ML-KEM-768") as kem:
        kem_pub = kem.generate_keypair()
        kem_cipher, _ = kem.encap_secret(kem_pub)
    mlkem_cipher_bytes  = len(kem_cipher)
    mlkem_pubkey_bytes  = len(kem_pub)

    # ── Classical baselines (NIST-standardised constants, widely cited) ───────
    # ECDSA P-256: DER-encoded signature = 70-72 bytes (use 71 midpoint)
    # ECDH P-256 ephemeral public key (uncompressed) = 65 bytes
    # ECDH P-256 shared secret = 32 bytes
    ecdsa_sig_bytes     = 71     # DER-encoded ECDSA-P256 signature
    ecdsa_pubkey_bytes  = 64     # Raw (x,y) public key (no prefix byte)
    ecdh_pubkey_bytes   = 65     # Uncompressed ECDH P-256 point
    ecdh_cipher_bytes   = 65     # ECDH "ciphertext" = ephemeral public key

    rows = [
        # Signatures
        ["ML-DSA-65 signature",         f"{mldsa_sig_bytes:,}",   "~71",         f"{mldsa_sig_bytes / ecdsa_sig_bytes:.1f}×"],
        ["ML-DSA-65 public key",        f"{mldsa_pubkey_bytes:,}", f"{ecdsa_pubkey_bytes}", f"{mldsa_pubkey_bytes / ecdsa_pubkey_bytes:.1f}×"],
        # KEM ciphertexts
        ["ML-KEM-768 ciphertext",       f"{mlkem_cipher_bytes:,}", f"{ecdh_cipher_bytes}", f"{mlkem_cipher_bytes / ecdh_cipher_bytes:.1f}×"],
        ["ML-KEM-768 public key",       f"{mlkem_pubkey_bytes:,}", f"{ecdh_pubkey_bytes}", f"{mlkem_pubkey_bytes / ecdh_pubkey_bytes:.1f}×"],
    ]

    print_table(
        headers=["Artefact", "PQC (bytes)", "Classical (bytes)", "Size Ratio"],
        rows=rows,
        title="PQC vs. Classical Artefact Size Comparison",
    )

    print(f"  Key insight: ML-DSA-65 signatures are {mldsa_sig_bytes/ecdsa_sig_bytes:.0f}× larger than ECDSA-P256.")
    print(f"  ML-KEM-768 ciphertexts are {mlkem_cipher_bytes/ecdh_cipher_bytes:.0f}× larger than ECDH ephemeral keys.")
    print(f"  These overheads appear in every published message envelope (see publisher.py).\n")

    save_csv(
        "size_overhead.csv",
        ["artefact", "pqc_bytes", "classical_bytes", "size_ratio"],
        [
            ["ML-DSA-65 signature",   mldsa_sig_bytes,   ecdsa_sig_bytes,   f"{mldsa_sig_bytes/ecdsa_sig_bytes:.2f}"],
            ["ML-DSA-65 public key",  mldsa_pubkey_bytes, ecdsa_pubkey_bytes, f"{mldsa_pubkey_bytes/ecdsa_pubkey_bytes:.2f}"],
            ["ML-KEM-768 ciphertext", mlkem_cipher_bytes, ecdh_cipher_bytes,  f"{mlkem_cipher_bytes/ecdh_cipher_bytes:.2f}"],
            ["ML-KEM-768 public key", mlkem_pubkey_bytes, ecdh_pubkey_bytes,  f"{mlkem_pubkey_bytes/ecdh_pubkey_bytes:.2f}"],
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="PQC Cryptographic Layer Benchmarks — research paper evaluation"
    )
    parser.add_argument(
        "--skip-tls", action="store_true",
        help="Skip TLS handshake trials (run crypto-only sections 2 & 3 offline)"
    )
    parser.add_argument(
        "--tls-trials", type=int, default=TLS_TRIALS,
        help=f"Number of TLS handshake trials per mode (default: {TLS_TRIALS})"
    )
    parser.add_argument(
        "--crypto-trials", type=int, default=CRYPTO_TRIALS,
        help=f"Number of sign/verify trials (default: {CRYPTO_TRIALS})"
    )
    args = parser.parse_args()

    if args.tls_trials <= 0 or args.crypto_trials <= 0:
        parser.error("--tls-trials and --crypto-trials must be greater than zero")

    save_metadata("pqc_bench_metadata.json", {
        "tls_trials": args.tls_trials,
        "crypto_trials": args.crypto_trials,
        "skip_tls": args.skip_tls,
        "tls_measurement": "TLS 1.3 mutual TLS vs TLS 1.2 ECDHE; not PQC TLS",
    })

    print("=" * 70)
    print("  PQC Cryptographic Layer Benchmarks")
    print("  For: Research Paper — IoT Data Sharing with PQC + Blockchain + FL")
    print("=" * 70)

    # Section 1
    if not args.skip_tls:
        bench_tls_handshake(n=args.tls_trials)
    else:
        print("\n[INFO] Skipping TLS handshake trials (--skip-tls flag set).")

    # Section 2
    bench_sign_verify(n=args.crypto_trials)

    # Section 3
    bench_sizes()

    print("=" * 70)
    print("  PQC benchmarks complete. Results in benchmarks/results/")
    print("=" * 70)


if __name__ == "__main__":
    main()

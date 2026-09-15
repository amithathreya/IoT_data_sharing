"""
blockchain_bench.py — Blockchain Layer Benchmarks
==================================================
Research paper Section: "Blockchain Write Latency & Throughput"

Measurements:
  1. Write Latency  : time from calling storeRecord() to receiving the
                      transaction receipt (web3.py wait_for_transaction_receipt)
                      → 20-30 sequential trials, mean/median/stddev in ms

  2. Throughput     : records/second under sustained load
                      → N concurrent threads hammering recordTelemetry()
                        over a configurable time window (default 60 s)
                      → reports confirmed TPS
                      → includes comparison table vs. Kumar et al. [5]
                        and Mishra & Vishnoi [9]

Usage:
  # Full benchmark (requires Besu at 127.0.0.1:8545 with contract deployed):
  python benchmarks/blockchain_bench.py

  # Adjust trials and load-test duration:
  python benchmarks/blockchain_bench.py --latency-trials 25 --throughput-secs 60

Run from the project root: d:/major_project_server/
"""

import argparse
import hashlib
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchmarks.bench_utils import banner, print_table, save_csv, save_metadata, stats

try:
    from web3 import Web3
    from dotenv import load_dotenv
except ImportError:
    print("[ERROR] web3 / python-dotenv not installed.")
    sys.exit(1)

try:
    import json
except ImportError:
    pass

# ─────────────────────────────────────────────────────────────────────────────
#  Configuration — mirrors server.py settings
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

BESU_RPC_URL     = "http://127.0.0.1:8545"
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "0x0000000000000000000000000000000000000000")
BESU_PRIVATE_KEY = os.getenv("BESU_PRIVATE_KEY",
                              "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63")
ABI_PATH         = Path(__file__).resolve().parent.parent / "contract_abi.json"

LATENCY_TRIALS   = 20   # sequential write trials for latency measurement
THROUGHPUT_SECS  = 60   # duration of load-test window (seconds)
THROUGHPUT_THREADS = 4  # concurrent sender threads


class NonceAllocator:
    """Allocate unique pending nonces for concurrent sends from one account."""
    def __init__(self, w3, account_address: str):
        self._w3 = w3
        self._account_address = account_address
        self._lock = threading.Lock()
        self._next_nonce = w3.eth.get_transaction_count(account_address, "pending")

    def reserve(self) -> int:
        with self._lock:
            nonce = self._next_nonce
            self._next_nonce += 1
            return nonce


def _connect():
    """Connect to Besu and return (w3, contract, account) or raise."""
    w3 = Web3(Web3.HTTPProvider(BESU_RPC_URL))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to Besu at {BESU_RPC_URL}. Is the node running?")

    account = w3.eth.account.from_key(BESU_PRIVATE_KEY)

    if not ABI_PATH.exists():
        raise FileNotFoundError(f"contract_abi.json not found at {ABI_PATH}. Run deploy.py first.")

    with open(ABI_PATH) as f:
        abi = json.load(f)

    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=abi)
    return w3, contract, account


def _send_one(w3, contract, account, node_id: str, nonce_override: int = None,
              on_submitted=None) -> float:
    """
    Call recordTelemetry() and wait for receipt.
    Returns the wall-clock write latency in milliseconds.
    Raises on failure.
    """
    ts_ns        = time.time_ns()
    payload_hash = hashlib.sha256(f"{node_id}{ts_ns}".encode()).digest()

    nonce = nonce_override if nonce_override is not None else \
            w3.eth.get_transaction_count(account.address, "pending")

    tx = contract.functions.recordTelemetry(
        node_id, ts_ns, payload_hash
    ).build_transaction({
        "chainId":  w3.eth.chain_id,
        "from":     account.address,
        "nonce":    nonce,
        "gas":      300_000,
        "gasPrice": w3.eth.gas_price,
    })

    signed = w3.eth.account.sign_transaction(tx, private_key=BESU_PRIVATE_KEY)

    t0 = time.perf_counter()
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    if on_submitted:
        on_submitted(tx_hash)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    t1 = time.perf_counter()

    if receipt.status != 1:
        raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")

    return (t1 - t0) * 1000.0  # ms


# ─────────────────────────────────────────────────────────────────────────────
#  Section 1 — Write Latency
# ─────────────────────────────────────────────────────────────────────────────

def bench_write_latency(n: int = LATENCY_TRIALS):
    banner(f"Section 1 — Blockchain Write Latency ({n} sequential trials)")

    try:
        w3, contract, account = _connect()
    except Exception as e:
        print(f"[ERROR] {e}")
        return None

    print(f"  Besu node:       {BESU_RPC_URL}")
    print(f"  Contract:        {CONTRACT_ADDRESS}")
    print(f"  Account:         {account.address}")
    print(f"  Chain ID:        {w3.eth.chain_id}\n")

    # Warm-up: 2 transactions to let the miner warm up
    print("  Warm-up: 2 transactions...")
    for _ in range(2):
        try:
            _send_one(w3, contract, account, "BENCH_WARMUP")
        except Exception as e:
            print(f"  [WARN] Warm-up failed: {e}")

    latencies_ms = []
    tx_hashes = []
    print(f"  Running {n} timed trials...")
    for i in range(n):
        try:
            lat = _send_one(w3, contract, account, f"BENCH_NODE_{i % 4}")
            latencies_ms.append(lat)
            pct = (i + 1) / n * 100
            print(f"  Trial {i+1:>3}/{n}  {lat:>8.1f} ms  [{pct:.0f}%]")
        except Exception as e:
            print(f"  [WARN] Trial {i} failed: {e}")

    if not latencies_ms:
        print("[ERROR] All latency trials failed.")
        return None

    s = stats(latencies_ms)

    print_table(
        headers=["Metric", "Value (ms)"],
        rows=[
            ["Mean",   f"{s['mean']:.1f}"],
            ["Median", f"{s['median']:.1f}"],
            ["StdDev", f"{s['stddev']:.1f}"],
            ["p95",    f"{s['p95']:.1f}"],
            ["Min",    f"{s['min']:.1f}"],
            ["Max",    f"{s['max']:.1f}"],
            ["Trials", str(s["n"])],
        ],
        title="Blockchain Write Latency (ms) — recordTelemetry() → receipt",
    )

    # Literature comparison
    print_table(
        headers=["System", "Validators", "Consensus", "Latency (ms)", "Source"],
        rows=[
            ["This work (Besu IBFT)",  "4",  "IBFT 2.0",  f"{s['mean']:.0f}",    "measured"],
            ["Kumar et al. [5]",       "15", "DPoS",       "~110",                "cited"],
            ["Mishra & Vishnoi [9]",   "5",  "PBFT",       "2000–3000",           "cited"],
        ],
        title="Latency Comparison Table (for paper)",
    )

    save_csv(
        "blockchain_latency.csv",
        ["trial", "latency_ms"],
        [[i + 1, f"{v:.4f}"] for i, v in enumerate(latencies_ms)],
    )
    save_csv(
        "blockchain_latency_summary.csv",
        ["metric", "value_ms"],
        [
            ["mean",   f"{s['mean']:.4f}"],
            ["median", f"{s['median']:.4f}"],
            ["stddev", f"{s['stddev']:.4f}"],
            ["p95",    f"{s['p95']:.4f}"],
            ["min",    f"{s['min']:.4f}"],
            ["max",    f"{s['max']:.4f}"],
            ["n",      s["n"]],
        ],
    )
    return s


# ─────────────────────────────────────────────────────────────────────────────
#  Section 2 — Throughput (Records/Second)
# ─────────────────────────────────────────────────────────────────────────────

def bench_throughput(duration_s: int = THROUGHPUT_SECS, n_threads: int = THROUGHPUT_THREADS):
    banner(f"Section 2 — Blockchain Throughput ({n_threads} threads, {duration_s}s window)")

    try:
        w3, contract, account = _connect()
    except Exception as e:
        print(f"[ERROR] {e}")
        return None

    print(f"  Hammering recordTelemetry() for {duration_s} seconds with {n_threads} threads...")
    print("  Only confirmed (status=1) receipts are counted.\n")

    # All workers use one account, so nonce assignment must be shared and atomic.
    nonce_allocator = NonceAllocator(w3, account.address)

    # Thread-safe counters
    confirmed_lock = threading.Lock()
    confirmed_count = [0]
    failed_count    = [0]
    submitted_count = [0]
    latencies_ms    = []

    stop_event = threading.Event()

    def worker(thread_id: int):
        """Each thread sends transactions as fast as it can until stop_event is set."""
        # Each thread has its own client connection; nonces remain centrally allocated.
        local_w3 = Web3(Web3.HTTPProvider(BESU_RPC_URL))
        local_account = local_w3.eth.account.from_key(BESU_PRIVATE_KEY)
        with open(ABI_PATH) as f:
            local_abi = json.load(f)
        local_contract = local_w3.eth.contract(address=CONTRACT_ADDRESS, abi=local_abi)

        while not stop_event.is_set():
            try:
                nonce = nonce_allocator.reserve()
                lat = _send_one(local_w3, local_contract, local_account,
                                f"LOAD_THREAD_{thread_id}", nonce_override=nonce,
                                on_submitted=lambda _: _count_submitted())
                with confirmed_lock:
                    confirmed_count[0] += 1
                    latencies_ms.append(lat)
            except Exception:
                with confirmed_lock:
                    failed_count[0] += 1

    def _count_submitted():
        with confirmed_lock:
            submitted_count[0] += 1

    threads = [threading.Thread(target=worker, args=(i,), daemon=True)
               for i in range(n_threads)]

    t_start = time.perf_counter()
    for t in threads:
        t.start()

    # Progress reporting
    last_report = 0
    while True:
        elapsed = time.perf_counter() - t_start
        if elapsed >= duration_s:
            break
        if int(elapsed) > last_report and int(elapsed) % 10 == 0:
            print(f"  {elapsed:>5.0f}s elapsed | confirmed: {confirmed_count[0]} | failed: {failed_count[0]}")
            last_report = int(elapsed)
        time.sleep(0.5)

    stop_event.set()
    for t in threads:
        t.join(timeout=15)

    t_elapsed = time.perf_counter() - t_start
    total_confirmed = confirmed_count[0]
    total_failed    = failed_count[0]
    tps             = total_confirmed / t_elapsed if t_elapsed > 0 else 0

    print_table(
        headers=["Metric", "Value"],
        rows=[
            ["Duration (s)",         f"{t_elapsed:.1f}"],
            ["Threads",              str(n_threads)],
            ["Submitted transactions", str(submitted_count[0])],
            ["Confirmed receipts",   str(total_confirmed)],
            ["Failed/dropped",       str(total_failed)],
            ["Throughput (TPS)",     f"{tps:.2f}"],
            ["Avg latency/tx (ms)",  f"{sum(latencies_ms)/len(latencies_ms):.1f}" if latencies_ms else "N/A"],
        ],
        title="Blockchain Throughput Results",
    )

    # Literature comparison
    print_table(
        headers=["System", "Validators", "Consensus", "TPS", "Source"],
        rows=[
            ["This work (Besu IBFT)",  "4",  "IBFT 2.0",  f"{tps:.1f}",    "measured"],
            ["Kumar et al. [5]",       "15", "DPoS",       "~2,200",        "cited (msg/s, not TPS)"],
            ["Mishra & Vishnoi [9]",   "5",  "PBFT",       "10–15",         "cited"],
        ],
        title="Throughput Comparison Table (for paper)",
    )

    save_csv(
        "blockchain_throughput.csv",
        ["duration_s", "threads", "submitted_txs", "confirmed_txs", "failed_txs", "tps", "avg_latency_ms"],
        [[f"{t_elapsed:.2f}", n_threads, submitted_count[0], total_confirmed, total_failed,
          f"{tps:.4f}", f"{sum(latencies_ms)/max(len(latencies_ms),1):.2f}"]],
    )
    return tps


# ─────────────────────────────────────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Blockchain Layer Benchmarks — research paper evaluation"
    )
    parser.add_argument("--latency-trials",   type=int, default=LATENCY_TRIALS,
                        help=f"Sequential write trials for latency (default: {LATENCY_TRIALS})")
    parser.add_argument("--throughput-secs",  type=int, default=THROUGHPUT_SECS,
                        help=f"Load-test window in seconds (default: {THROUGHPUT_SECS})")
    parser.add_argument("--throughput-threads", type=int, default=THROUGHPUT_THREADS,
                        help=f"Concurrent sender threads (default: {THROUGHPUT_THREADS})")
    parser.add_argument("--skip-throughput",  action="store_true",
                        help="Skip the throughput load-test (run latency only)")
    args = parser.parse_args()

    if args.latency_trials <= 0:
        parser.error("--latency-trials must be greater than zero")
    if args.throughput_secs <= 0:
        parser.error("--throughput-secs must be greater than zero")
    if args.throughput_threads <= 0:
        parser.error("--throughput-threads must be greater than zero")

    save_metadata("blockchain_bench_metadata.json", {
        "latency_trials": args.latency_trials,
        "throughput_secs": args.throughput_secs,
        "throughput_threads": args.throughput_threads,
        "rpc_url": BESU_RPC_URL,
        "contract_address": CONTRACT_ADDRESS,
    })

    print("=" * 70)
    print("  Blockchain Layer Benchmarks")
    print("  For: Research Paper — IoT Data Sharing with PQC + Blockchain + FL")
    print("=" * 70)

    bench_write_latency(n=args.latency_trials)

    if not args.skip_throughput:
        bench_throughput(duration_s=args.throughput_secs,
                         n_threads=args.throughput_threads)
    else:
        print("\n[INFO] Skipping throughput test (--skip-throughput flag set).")

    print("=" * 70)
    print("  Blockchain benchmarks complete. Results in benchmarks/results/")
    print("=" * 70)


if __name__ == "__main__":
    main()

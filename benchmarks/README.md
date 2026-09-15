# Benchmark Scripts for Research Paper

This folder contains all evaluation scripts for the research paper:
**"Secure IoT Data Sharing with Post-Quantum Cryptography, Blockchain, and Federated Learning"**

---

## Scripts

| Script | Requires | Section in Paper |
|--------|----------|-----------------|
| [`pqc_bench.py`](pqc_bench.py) | RabbitMQ (for TLS section only) | §PQC layer + classical TLS comparison |
| [`blockchain_bench.py`](blockchain_bench.py) | Besu at `127.0.0.1:8545`, contract deployed | §Blockchain Layer |
| [`xfl_bench.py`](xfl_bench.py) | None (fully offline) | §XFL Layer |
| [`resource_monitor.py`](resource_monitor.py) | None (offline, run on Pi) | §Resource Constraints |

All scripts write output to `benchmarks/results/`.

---

## Quick Start

```powershell
# From project root (d:\major_project_server)

# 1. PQC benchmarks — crypto sections run offline; TLS section needs RabbitMQ
python benchmarks/pqc_bench.py --skip-tls          # offline-only (sections 2 & 3)
python benchmarks/pqc_bench.py --tls-trials 50      # full (with RabbitMQ running)

# 2. Blockchain benchmarks — requires Besu + deployed contract
python benchmarks/blockchain_bench.py --latency-trials 20 --throughput-secs 60

# 3. XFL benchmarks — fully offline
python benchmarks/xfl_bench.py --rounds 15 --clients 2 --runs 3 --seed 42

# 4. Resource profiling — run on Pi for paper numbers
python benchmarks/resource_monitor.py --idle-secs 10 --sign-trials 50
```

---

## Output Files

| File | Contents |
|------|----------|
| `results/tls_handshake_results.csv` | Classical TLS 1.3 mutual-TLS vs TLS 1.2/ECDHE handshake times (not PQC TLS) |
| `results/sign_verify_latency.csv` | ML-DSA-65 sign/verify mean/median/stddev (μs) |
| `results/size_overhead.csv` | PQC vs classical artefact byte sizes |
| `results/blockchain_latency.csv` | Per-trial write latency (ms) |
| `results/blockchain_latency_summary.csv` | Mean/median/stddev/p95 write latency |
| `results/blockchain_throughput.csv` | TPS under concurrent load |
| `results/xfl_loss_curves.csv` | (round, xfl_loss, fedavg_loss) per round |
| `results/xfl_communication.csv` | Bytes/round for XFL vs FedAvg |
| `results/xfl_summary.csv` | Communication reduction %, convergence rounds |
| `results/xfl_loss_curve.png` | Loss curve + communication volume plot |
| `results/resource_results.csv` | Mean/peak CPU%, memory by phase |
| `results/resource_timeline_raw.csv` | Raw (time, cpu, mem) samples for custom plotting |
| `results/resource_timeline.png` | CPU & memory timeline across all three phases |
| `results/*_metadata.json` | Parameters, timestamp, Git revision, Python, and host-platform metadata |

---

## Paper Comparison Points

### Blockchain (cited in the paper)
| System | Validators | Consensus | Latency | TPS | Source |
|--------|-----------|-----------|---------|-----|--------|
| **This work** | 4 | IBFT 2.0 | *measured* | *measured* | `blockchain_bench.py` |
| Kumar et al. [5] | 15 | DPoS | ~110 ms | ~2,200 msg/s | cited |
| Mishra & Vishnoi [9] | 5 | PBFT | 2–3 s | 10–15 TPS | cited |

### PQC Sizes
| Artefact | PQC | Classical |
|----------|-----|-----------|
| Signature | ML-DSA-65 ~3,309 B | ECDSA-P256 ~71 B |
| KEM ciphertext | ML-KEM-768 ~1,088 B | ECDH P-256 ~65 B |

---

## Notes for Pi Deployment

```bash
# Copy benchmark folder to Pi
scp -r benchmarks/ pi@<PI_IP>:/home/pi/pqc_project/

# On the Pi, install deps if not present
pip install numpy psutil oqs tensorflow

# Run resource monitor directly on Pi hardware
python3 benchmarks/resource_monitor.py
```

> CPU readings from `resource_monitor.py` reflect the machine it runs on.
> For accurate Pi numbers, run it **on the Pi**, not the Windows server.

"""
resource_monitor.py — Pi Resource Usage Profiler
=================================================
Research paper Section: "Resource Constraints on IoT Devices"

Profiles CPU % and memory (RSS MB) during three phases:
  (a) Idle           — 10-second baseline, no workload
  (b) Sign + Publish — ML-DSA-65 burst signing (50 operations) + psutil sampling
  (c) FL Training    — one XFL local training epoch on synthetic data

Output:
  → Console summary table  (mean / peak CPU % and memory MB per phase)
  → benchmarks/results/resource_results.csv
  → benchmarks/results/resource_timeline.png  (time-series plot if matplotlib installed)

Notes:
  • Designed to be scp'd to the Raspberry Pi for paper-quality numbers.
  • Runs on Windows too but CPU% will reflect the host machine, not the Pi.
  • Sampling interval is 0.5 s (configurable with --sample-interval).

Usage:
  python benchmarks/resource_monitor.py
  python benchmarks/resource_monitor.py --idle-secs 15 --sign-trials 100
"""

import argparse
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchmarks.bench_utils import banner, ensure_results_dir, print_table, save_csv, save_metadata

try:
    import psutil
except ImportError:
    print("[ERROR] psutil not installed. Run: pip install psutil")
    sys.exit(1)

try:
    import numpy as np
except ImportError:
    print("[ERROR] numpy not installed. Run: pip install numpy")
    sys.exit(1)

try:
    import oqs
    OQS_OK = True
except ImportError:
    print("[WARN] liboqs-python not installed. Signing phase will be skipped.")
    OQS_OK = False

try:
    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
    TF_OK = True
except ImportError:
    print("[WARN] tensorflow not installed. FL training phase will be skipped.")
    TF_OK = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False

# ─────────────────────────────────────────────────────────────────────────────
#  Defaults
# ─────────────────────────────────────────────────────────────────────────────
IDLE_SECS       = 10     # baseline idle measurement window
SIGN_TRIALS     = 50     # number of ML-DSA-65 sign ops in phase (b)
SAMPLE_INTERVAL = 0.5    # psutil sampling interval (seconds)

PROCESS = psutil.Process(os.getpid())


# ─────────────────────────────────────────────────────────────────────────────
#  Sampler thread
# ─────────────────────────────────────────────────────────────────────────────

class ResourceSampler:
    """
    Background thread that records (timestamp, cpu_pct, rss_mb) tuples
    at a fixed interval while a workload runs in the foreground.
    """
    def __init__(self, interval: float = SAMPLE_INTERVAL):
        self.interval = interval
        self.samples  = []          # list of (rel_time_s, cpu_pct, rss_mb)
        self._stop    = threading.Event()
        self._thread  = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._t0 = time.perf_counter()
        # Prime cpu_percent() so the first sample is non-zero
        PROCESS.cpu_percent(interval=None)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=5)

    def _run(self):
        while not self._stop.is_set():
            try:
                cpu  = PROCESS.cpu_percent(interval=None)
                mem  = PROCESS.memory_info().rss / (1024 * 1024)  # MB
                rel  = time.perf_counter() - self._t0
                self.samples.append((round(rel, 3), round(cpu, 2), round(mem, 2)))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            time.sleep(self.interval)

    def summary(self) -> dict:
        if not self.samples:
            return {"mean_cpu": 0.0, "peak_cpu": 0.0, "mean_mem": 0.0, "peak_mem": 0.0, "n": 0}
        cpu_vals = [s[1] for s in self.samples]
        mem_vals = [s[2] for s in self.samples]
        return {
            "mean_cpu": round(float(np.mean(cpu_vals)), 2),
            "peak_cpu": round(float(np.max(cpu_vals)),  2),
            "mean_mem": round(float(np.mean(mem_vals)), 2),
            "peak_mem": round(float(np.max(mem_vals)),  2),
            "n":        len(self.samples),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Phase (a) — Idle
# ─────────────────────────────────────────────────────────────────────────────

def phase_idle(secs: int, sample_interval: float) -> tuple:
    banner(f"Phase (a) — Idle Baseline ({secs} seconds)")
    print(f"  No workload. Sampling CPU & memory every {sample_interval}s...")
    sampler = ResourceSampler(sample_interval)
    phase_start = time.perf_counter()
    sampler.start()
    time.sleep(secs)
    sampler.stop()
    s = sampler.summary()
    s["duration_s"] = round(time.perf_counter() - phase_start, 3)
    print(f"  Done. {s['n']} samples collected.")
    return s, sampler.samples


# ─────────────────────────────────────────────────────────────────────────────
#  Phase (b) — Sign + Publish (ML-DSA-65 burst)
# ─────────────────────────────────────────────────────────────────────────────

def phase_sign(n: int, sample_interval: float) -> tuple:
    banner(f"Phase (b) — ML-DSA-65 Signing + Publishing ({n} sign operations)")

    if not OQS_OK:
        print("  [SKIP] liboqs not available.")
        return {"mean_cpu": 0, "peak_cpu": 0, "mean_mem": 0, "peak_mem": 0, "n": 0, "duration_s": 0}, []

    signer     = oqs.Signature("ML-DSA-65")
    pub_key    = signer.generate_keypair()
    priv_key   = signer.export_secret_key()
    auth_data  = os.urandom(1088 + 12 + 350)   # realistic auth blob

    sampler = ResourceSampler(sample_interval)
    phase_start = time.perf_counter()
    sampler.start()

    sign_times_ms = []
    print(f"  Running {n} sign() calls...")
    for i in range(n):
        with oqs.Signature("ML-DSA-65", priv_key) as s:
            t0  = time.perf_counter()
            sig = s.sign(auth_data)
            t1  = time.perf_counter()
        sign_times_ms.append((t1 - t0) * 1000)

        # Simulate the 2.5-second publish cadence of publisher.py (scaled down)
        # We sleep 0.1s between signs so sampling captures steady-state CPU load
        time.sleep(0.1)

        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{n} signs completed...")

    sampler.stop()
    s = sampler.summary()
    s["duration_s"] = round(time.perf_counter() - phase_start, 3)
    avg_sign_ms = float(np.mean(sign_times_ms))
    print(f"\n  Avg sign latency during profiling: {avg_sign_ms:.2f} ms")
    print(f"  {s['n']} resource samples collected.")
    return s, sampler.samples


# ─────────────────────────────────────────────────────────────────────────────
#  Phase (c) — FL Local Training (one XFL round)
# ─────────────────────────────────────────────────────────────────────────────

def _get_fl_model():
    return tf.keras.models.Sequential([
        tf.keras.layers.Dense(16, activation="relu", input_shape=(20,), name="enc_1"),
        tf.keras.layers.Dense(8,  activation="relu",  name="enc_2"),
        tf.keras.layers.Dense(16, activation="relu",  name="dec_1"),
        tf.keras.layers.Dense(20, name="output"),
    ])


def phase_fl_training(sample_interval: float) -> tuple:
    banner("Phase (c) — FL Local Training (one XFL training round on synthetic data)")

    if not TF_OK:
        print("  [SKIP] TensorFlow not available.")
        return {"mean_cpu": 0, "peak_cpu": 0, "mean_mem": 0, "peak_mem": 0, "n": 0, "duration_s": 0}, []

    rng    = np.random.default_rng(99)
    x_data = rng.uniform(0.40, 0.65, size=(200, 20)).astype(np.float32)
    model  = _get_fl_model()
    model.compile(optimizer="adam", loss="mse")

    sampler = ResourceSampler(sample_interval)
    phase_start = time.perf_counter()
    sampler.start()

    print("  Training autoencoder (5 epochs, batch_size=16)...")
    t0 = time.perf_counter()
    history = model.fit(
        x_data, x_data,
        epochs=5, batch_size=16,
        verbose=1,
    )
    t1 = time.perf_counter()

    sampler.stop()
    s = sampler.summary()
    s["duration_s"] = round(time.perf_counter() - phase_start, 3)
    train_secs = t1 - t0
    final_loss = history.history["loss"][-1]

    print(f"\n  Training time : {train_secs:.2f} s")
    print(f"  Final MSE loss: {final_loss:.5f}")
    print(f"  {s['n']} resource samples collected.")
    return s, sampler.samples


# ─────────────────────────────────────────────────────────────────────────────
#  Plotting
# ─────────────────────────────────────────────────────────────────────────────

def plot_timeline(phases_samples: dict, save_dir: str):
    if not MATPLOTLIB_OK:
        print("[WARN] Skipping timeline plot (matplotlib not available).")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=False)
    fig.suptitle("Resource Usage Timeline — Raspberry Pi (or Host)\n"
                 "(a) Idle  |  (b) Signing+Publishing  |  (c) FL Training",
                 fontsize=13, fontweight="bold")

    colours = {"(a) Idle": "#2ecc71", "(b) Signing": "#e67e22", "(c) FL Training": "#3498db"}

    for phase_name, samples in phases_samples.items():
        if not samples:
            continue
        t   = [s[0] for s in samples]
        cpu = [s[1] for s in samples]
        mem = [s[2] for s in samples]
        col = colours.get(phase_name, "grey")
        ax1.plot(t, cpu, label=phase_name, color=col, linewidth=1.5)
        ax2.plot(t, mem, label=phase_name, color=col, linewidth=1.5)

    ax1.set_ylabel("CPU Usage (%)", fontsize=11)
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(bottom=0)

    ax2.set_ylabel("Memory RSS (MB)", fontsize=11)
    ax2.set_xlabel("Time (s)", fontsize=11)
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    path = os.path.join(save_dir, "resource_timeline.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n[resource_monitor] Timeline plot saved → {path}")


# ─────────────────────────────────────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Pi Resource Monitor — research paper evaluation"
    )
    parser.add_argument("--idle-secs",       type=int,   default=IDLE_SECS,
                        help=f"Idle baseline duration in seconds (default: {IDLE_SECS})")
    parser.add_argument("--sign-trials",     type=int,   default=SIGN_TRIALS,
                        help=f"Sign operations in phase (b) (default: {SIGN_TRIALS})")
    parser.add_argument("--sample-interval", type=float, default=SAMPLE_INTERVAL,
                        help=f"psutil sampling interval in seconds (default: {SAMPLE_INTERVAL})")
    parser.add_argument("--min-samples", type=int, default=20,
                        help="Warn when a phase collects fewer samples than this (default: 20)")
    args = parser.parse_args()

    if args.idle_secs <= 0 or args.sign_trials <= 0:
        parser.error("--idle-secs and --sign-trials must be greater than zero")
    if args.sample_interval <= 0 or args.min_samples <= 0:
        parser.error("--sample-interval and --min-samples must be greater than zero")

    save_metadata("resource_monitor_metadata.json", {
        "idle_secs": args.idle_secs,
        "sign_trials": args.sign_trials,
        "sample_interval_s": args.sample_interval,
        "min_samples": args.min_samples,
    })

    print("=" * 70)
    print("  Resource Usage Profiler")
    print("  For: Research Paper — IoT Data Sharing with PQC + Blockchain + FL")
    print(f"  Platform: {sys.platform} | PID: {os.getpid()}")
    print("=" * 70)

    s_idle, samp_idle = phase_idle(secs=args.idle_secs, sample_interval=args.sample_interval)
    s_sign, samp_sign = phase_sign(n=args.sign_trials, sample_interval=args.sample_interval)
    s_fl,   samp_fl   = phase_fl_training(sample_interval=args.sample_interval)

    for name, summary in [("idle", s_idle), ("signing", s_sign), ("fl_training", s_fl)]:
        if summary["n"] < args.min_samples:
            print(f"[WARN] {name} collected only {summary['n']} samples; "
                  f"increase workload duration or reduce --sample-interval before reporting means.")

    # ── Summary table ────────────────────────────────────────────────────────
    banner("Resource Usage Summary (all phases)")

    print_table(
        headers=["Phase", "Duration (s)", "Mean CPU %", "Peak CPU %", "Mean Mem (MB)", "Peak Mem (MB)", "Samples"],
        rows=[
            ["(a) Idle",          s_idle["duration_s"], s_idle["mean_cpu"], s_idle["peak_cpu"],
             s_idle["mean_mem"],  s_idle["peak_mem"],  s_idle["n"]],
            ["(b) Signing",       s_sign["duration_s"], s_sign["mean_cpu"], s_sign["peak_cpu"],
             s_sign["mean_mem"],  s_sign["peak_mem"],  s_sign["n"]],
            ["(c) FL Training",   s_fl["duration_s"], s_fl["mean_cpu"],   s_fl["peak_cpu"],
             s_fl["mean_mem"],    s_fl["peak_mem"],    s_fl["n"]],
        ],
        title="CPU & Memory — Phase Comparison",
    )

    print("  Note: For the paper, run this script on the Raspberry Pi.")
    print("  On Pi, CPU% > 100% is possible with multi-core (Pi 4 has 4 cores).")
    print("  Peak CPU during signing is the key reviewer-expected metric.\n")

    # ── Save results ─────────────────────────────────────────────────────────
    results_dir = ensure_results_dir()

    save_csv(
        "resource_results.csv",
        ["phase", "duration_s", "mean_cpu_pct", "peak_cpu_pct", "mean_mem_mb", "peak_mem_mb", "n_samples"],
        [
            ["idle",        s_idle["duration_s"], s_idle["mean_cpu"], s_idle["peak_cpu"], s_idle["mean_mem"], s_idle["peak_mem"], s_idle["n"]],
            ["signing",     s_sign["duration_s"], s_sign["mean_cpu"], s_sign["peak_cpu"], s_sign["mean_mem"], s_sign["peak_mem"], s_sign["n"]],
            ["fl_training", s_fl["duration_s"], s_fl["mean_cpu"],   s_fl["peak_cpu"],   s_fl["mean_mem"],   s_fl["peak_mem"],   s_fl["n"]],
        ],
    )

    # Offset phase-local timestamps so the saved/plot timeline is continuous.
    offset = 0.0
    timeline_samples = {}
    for phase_name, samples in [("(a) Idle", samp_idle), ("(b) Signing", samp_sign), ("(c) FL Training", samp_fl)]:
        shifted = [(round(t + offset, 3), cpu, mem) for t, cpu, mem in samples]
        timeline_samples[phase_name] = shifted
        if shifted:
            offset = shifted[-1][0] + args.sample_interval

    # Save raw timeline data for custom plotting
    all_raw = []
    for phase_name, samples in [("idle", timeline_samples["(a) Idle"]),
                                ("signing", timeline_samples["(b) Signing"]),
                                ("fl_training", timeline_samples["(c) FL Training"])]:
        for t, cpu, mem in samples:
            all_raw.append([phase_name, t, cpu, mem])

    save_csv(
        "resource_timeline_raw.csv",
        ["phase", "rel_time_s", "cpu_pct", "mem_mb"],
        all_raw,
    )

    # ── Plot ─────────────────────────────────────────────────────────────────
    plot_timeline(
        timeline_samples,
        results_dir,
    )

    print("=" * 70)
    print("  Resource profiling complete. Results in benchmarks/results/")
    print("=" * 70)


if __name__ == "__main__":
    main()

"""
xfl_bench.py — XFL / Federated Learning Benchmarks
====================================================
Research paper Section: "XFL Communication Efficiency & Convergence"

Measurements:
  1. Rounds to Convergence & Loss Curves
       → Simulates N FL rounds locally using synthetic network I/O data
         (no RabbitMQ needed — pure offline simulation)
       → Runs both XFL (BCS layer-wise sparse delta) and vanilla FedAvg
       → Records (round, loss) per round for both strategies
       → Saves loss-curve plot as benchmarks/results/xfl_loss_curve.png

  2. Per-Round Communication Volume
       → XFL (BCS):    only layer deltas above threshold are transmitted
       → FedAvg:       full model weights every round
       → Reports bytes/round for each strategy and the % reduction
       → This is the core efficiency claim reviewers will ask for first

  Architecture note:
    The live system (client_xfl.py) currently sends full weights and uses
    coordinate-wise median aggregation. This script is an OFFLINE BCS/FedAvg
    simulation, not a measurement of the deployed FL protocol.

Usage:
  python benchmarks/xfl_bench.py

  # Adjust rounds, clients, BCS threshold:
  python benchmarks/xfl_bench.py --rounds 20 --clients 2 --bcs-threshold 1e-4

Run from the project root: d:/major_project_server/
"""

import argparse
import os
import pickle
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchmarks.bench_utils import banner, ensure_results_dir, print_table, save_csv, save_metadata, stats

try:
    import numpy as np
except ImportError:
    print("[ERROR] numpy not installed. Run: pip install numpy")
    sys.exit(1)

try:
    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
except ImportError:
    print("[ERROR] tensorflow not installed. Run: pip install tensorflow")
    sys.exit(1)

try:
    import matplotlib
    matplotlib.use("Agg")  # headless — no display needed
    import matplotlib.pyplot as plt
    MATPLOTLIB_OK = True
except ImportError:
    print("[WARN] matplotlib not installed. Loss curves will not be plotted.")
    MATPLOTLIB_OK = False


# ─────────────────────────────────────────────────────────────────────────────
#  Hyperparameters
# ─────────────────────────────────────────────────────────────────────────────
FL_ROUNDS           = 15     # total FL rounds to simulate
NUM_CLIENTS         = 2      # simulated clients
LOCAL_EPOCHS        = 5      # local training epochs per round
BATCH_SIZE          = 16
BCS_DELTA_THRESHOLD = 1e-3   # BCS sparsification threshold (|Δw| > θ is sent)
INPUT_SHAPE         = (20,)  # input feature dimension (matches publisher.py)

# Optional larger model for sensitivity experiments. The default is the live
# client architecture, so its dense payload size matches the deployed client.
LARGE_HIDDEN = [128, 64, 32, 64]   # encoder / bottleneck / decoder widths


# ─────────────────────────────────────────────────────────────────────────────
#  Model factory
# ─────────────────────────────────────────────────────────────────────────────

def get_model(large: bool = False):
    """
    large=False (default): deployed 16-8-16-20 client autoencoder.
    large=True (--large-model): offline sensitivity model only.
    """
    if large:
        hidden = LARGE_HIDDEN
        m = tf.keras.models.Sequential([
            tf.keras.layers.Dense(hidden[0], activation="relu", input_shape=INPUT_SHAPE, name="enc_1"),
            tf.keras.layers.Dense(hidden[1], activation="relu", name="enc_2"),
            tf.keras.layers.Dense(hidden[2], activation="relu", name="bottleneck"),
            tf.keras.layers.Dense(hidden[3], activation="relu", name="dec_1"),
            tf.keras.layers.Dense(INPUT_SHAPE[0], name="output"),
        ])
    else:
        m = tf.keras.models.Sequential([
            tf.keras.layers.Dense(16, activation="relu", input_shape=INPUT_SHAPE, name="enc_1"),
            tf.keras.layers.Dense(8,  activation="relu", name="enc_2"),
            tf.keras.layers.Dense(16, activation="relu", name="dec_1"),
            tf.keras.layers.Dense(INPUT_SHAPE[0], name="output"),
        ])
    m.compile(optimizer="adam", loss="mse")
    return m


# ─────────────────────────────────────────────────────────────────────────────
#  Synthetic data generator — mirrors NetworkMonitor in client_xfl.py
# ─────────────────────────────────────────────────────────────────────────────

def make_synthetic_data(n_samples: int = 200, seed: int = 42) -> np.ndarray:
    """
    Generate synthetic log-scaled network I/O sequences.
    Normal traffic: scaled values in [0.40, 0.65]
    Anomalies (10% of samples): spikes to [0.80, 1.20]
    """
    rng   = np.random.default_rng(seed)
    data  = []
    for _ in range(n_samples):
        if rng.random() < 0.10:
            # Anomaly spike
            row = rng.uniform(0.80, 1.20, size=INPUT_SHAPE[0])
        else:
            row = rng.uniform(0.40, 0.65, size=INPUT_SHAPE[0])
        data.append(row)
    return np.array(data, dtype=np.float32)


# ─────────────────────────────────────────────────────────────────────────────
#  BCS (Broadcast-Compressed Sparsification) delta computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_bcs_delta(old_weights: list, new_weights: list, threshold: float):
    """
    Compute the sparse delta between two sets of weights using BCS.
    Returns:
      sparse_coo   : list of (flat_indices, values) tuples — only nonzero entries
      dense_delta  : list of dense arrays — used by the aggregation step
      sparsity_pct : percentage of parameters set to zero (not transmitted)
    """
    sparse_coo  = []
    dense_delta = []
    total    = 0
    nonzero  = 0
    for old_w, new_w in zip(old_weights, new_weights):
        diff = new_w - old_w
        mask = np.abs(diff) > threshold
        idxs = np.flatnonzero(mask)
        vals = diff.ravel()[idxs]
        sparse_coo.append((idxs, vals))
        # Reconstruct dense delta for aggregation
        dense_diff = np.zeros_like(diff)
        dense_diff.ravel()[idxs] = vals
        dense_delta.append(dense_diff)
        total   += diff.size
        nonzero += len(idxs)
    sparsity_pct = (1.0 - nonzero / max(total, 1)) * 100.0
    return sparse_coo, dense_delta, sparsity_pct


def serialized_size_sparse(sparse_coo: list) -> int:
    """
    Byte length of the sparse COO representation (indices + values).
    This is what actually goes on the wire in BCS transmission.
    """
    return len(pickle.dumps(sparse_coo))


def serialized_size(weights: list) -> int:
    """Return byte length of pickle-serialised dense weights (FedAvg wire size)."""
    return len(pickle.dumps(weights))


# ─────────────────────────────────────────────────────────────────────────────
#  FedAvg aggregation
# ─────────────────────────────────────────────────────────────────────────────

def fedavg(client_weights: list) -> list:
    """Coordinate-wise mean (standard FedAvg)."""
    return [np.mean(np.stack([cw[i] for cw in client_weights]), axis=0)
            for i in range(len(client_weights[0]))]


# ─────────────────────────────────────────────────────────────────────────────
#  Section 1 + 2 combined — Simulate FL and measure both convergence & comms
# ─────────────────────────────────────────────────────────────────────────────

def run_fl_simulation(
    strategy: str,          # "XFL_BCS" or "FedAvg"
    rounds: int,
    n_clients: int,
    local_epochs: int,
    bcs_threshold: float,
    initial_weights: list,
    datasets: list,
    large_model: bool,
):
    """
    Run a complete FL simulation for the given strategy.
    Returns a dict with:
      round_losses     : list of (round, avg_loss) tuples
      bytes_per_round  : list of bytes transmitted per round (all clients)
      sparsity_per_round: list of % zeros per round (XFL only)
    """
    print(f"\n  Strategy: {strategy}")
    print(f"  Rounds: {rounds} | Clients: {n_clients} | Local epochs: {local_epochs}")
    if strategy == "XFL_BCS":
        print(f"  BCS threshold: {bcs_threshold}\n")

    # Both strategies receive the same starting model and client datasets.
    global_weights = [w.copy() for w in initial_weights]

    round_losses      = []
    bytes_per_round   = []
    sparsity_per_round = []

    for rnd in range(1, rounds + 1):
        client_weights_list = []
        client_losses       = []
        round_bytes         = 0
        round_sparsity      = []

        for cid in range(n_clients):
            # Each client starts from global weights
            client_model = get_model(large=large_model)
            client_model.set_weights([w.copy() for w in global_weights])

            x_data = datasets[cid]
            history = client_model.fit(
                x_data, x_data,
                epochs=local_epochs,
                batch_size=BATCH_SIZE,
                verbose=0,
            )
            final_loss = history.history["loss"][-1]
            client_losses.append(final_loss)

            new_weights = client_model.get_weights()

            if strategy == "XFL_BCS":
                sparse_coo, dense_delta, sparsity = compute_bcs_delta(
                    global_weights, new_weights, bcs_threshold
                )
                # Transmit only sparse COO; aggregate using dense_delta
                client_weights_list.append(dense_delta)
                round_sparsity.append(sparsity)
                round_bytes += serialized_size_sparse(sparse_coo)
            else:
                # FedAvg: send full dense weights
                client_weights_list.append(new_weights)
                round_bytes += serialized_size(new_weights)

        # ── Aggregation ────────────────────────────────────────────────────
        if strategy == "XFL_BCS":
            # Apply deltas to global model
            avg_delta = fedavg(client_weights_list)
            global_weights = [gw + dw for gw, dw in zip(global_weights, avg_delta)]
        else:
            global_weights = fedavg(client_weights_list)

        avg_loss = float(np.mean(client_losses))
        avg_sparsity = float(np.mean(round_sparsity)) if round_sparsity else 0.0

        round_losses.append((rnd, avg_loss))
        bytes_per_round.append(round_bytes)
        sparsity_per_round.append(avg_sparsity)

        print(f"  Round {rnd:>3}/{rounds}  loss: {avg_loss:.5f}  "
              f"bytes/round: {round_bytes:,}"
              + (f"  sparsity: {avg_sparsity:.1f}%" if strategy == "XFL_BCS" else ""))

    return {
        "round_losses":      round_losses,
        "bytes_per_round":   bytes_per_round,
        "sparsity_per_round": sparsity_per_round,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Plotting
# ─────────────────────────────────────────────────────────────────────────────

def plot_results(xfl_results: dict, fedavg_results: dict, save_dir: str):
    if not MATPLOTLIB_OK:
        print("[WARN] Skipping plot generation (matplotlib not available).")
        return

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("XFL vs. FedAvg — FL Simulation Results", fontsize=14, fontweight="bold")

    # ── Loss Curve ──────────────────────────────────────────────────────────
    ax = axes[0]
    xfl_rounds    = [r for r, _ in xfl_results["round_losses"]]
    xfl_losses    = [l for _, l in xfl_results["round_losses"]]
    fedavg_rounds = [r for r, _ in fedavg_results["round_losses"]]
    fedavg_losses = [l for _, l in fedavg_results["round_losses"]]

    ax.plot(xfl_rounds,    xfl_losses,    "b-o", linewidth=2, markersize=5, label="XFL (BCS)")
    ax.plot(fedavg_rounds, fedavg_losses, "r--s", linewidth=2, markersize=5, label="FedAvg")
    ax.set_xlabel("FL Round", fontsize=11)
    ax.set_ylabel("Average Reconstruction Loss (MSE)", fontsize=11)
    ax.set_title("Convergence — Loss per Round", fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_yscale("log")

    # ── Communication Volume ─────────────────────────────────────────────────
    ax2 = axes[1]
    ax2.plot(xfl_rounds,    [b / 1024 for b in xfl_results["bytes_per_round"]],
             "b-o", linewidth=2, markersize=5, label="XFL (BCS)")
    ax2.plot(fedavg_rounds, [b / 1024 for b in fedavg_results["bytes_per_round"]],
             "r--s", linewidth=2, markersize=5, label="FedAvg")
    ax2.set_xlabel("FL Round", fontsize=11)
    ax2.set_ylabel("Bytes Transmitted / Round (KB)", fontsize=11)
    ax2.set_title("Communication Volume per Round", fontsize=12)
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plot_path = os.path.join(save_dir, "xfl_loss_curve.png")
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n[xfl_bench] Loss-curve plot saved → {plot_path}")


# ─────────────────────────────────────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def _run_once(args, seed: int):
    """Run paired strategies from identical initial weights and datasets."""
    tf.keras.utils.set_random_seed(seed)
    template = get_model(large=args.large_model)
    initial_weights = [w.copy() for w in template.get_weights()]
    datasets = [make_synthetic_data(n_samples=150 + i * 50, seed=seed + i + 1)
                for i in range(args.clients)]

    banner(f"Run seed {seed}: XFL (BCS) simulation")
    xfl_results = run_fl_simulation(
        strategy="XFL_BCS", rounds=args.rounds, n_clients=args.clients,
        local_epochs=args.local_epochs, bcs_threshold=args.bcs_threshold,
        initial_weights=initial_weights, datasets=datasets, large_model=args.large_model,
    )
    banner(f"Run seed {seed}: FedAvg simulation")
    fedavg_results = run_fl_simulation(
        strategy="FedAvg", rounds=args.rounds, n_clients=args.clients,
        local_epochs=args.local_epochs, bcs_threshold=args.bcs_threshold,
        initial_weights=initial_weights, datasets=datasets, large_model=args.large_model,
    )

    xfl_mean = float(np.mean(xfl_results["bytes_per_round"]))
    fedavg_mean = float(np.mean(fedavg_results["bytes_per_round"]))
    return {
        "seed": seed,
        "xfl": xfl_results,
        "fedavg": fedavg_results,
        "xfl_mean_bytes": xfl_mean,
        "fedavg_mean_bytes": fedavg_mean,
        "reduction_pct": (1 - xfl_mean / fedavg_mean) * 100 if fedavg_mean else 0.0,
    }


def main():
    parser = argparse.ArgumentParser(
        description="XFL / Federated Learning Benchmarks — research paper evaluation"
    )
    parser.add_argument("--rounds",        type=int,   default=FL_ROUNDS,
                        help=f"FL rounds to simulate (default: {FL_ROUNDS})")
    parser.add_argument("--clients",       type=int,   default=NUM_CLIENTS,
                        help=f"Simulated clients (default: {NUM_CLIENTS})")
    parser.add_argument("--local-epochs",  type=int,   default=LOCAL_EPOCHS,
                        help=f"Local training epochs per round (default: {LOCAL_EPOCHS})")
    parser.add_argument("--bcs-threshold", type=float, default=BCS_DELTA_THRESHOLD,
                        help=f"BCS sparsification threshold (default: {BCS_DELTA_THRESHOLD})")
    parser.add_argument("--seed", type=int, default=42,
                        help="Base random seed for reproducible paired runs (default: 42)")
    parser.add_argument("--runs", type=int, default=3,
                        help="Number of paired runs using consecutive seeds (default: 3)")
    parser.add_argument("--large-model", action="store_true",
                        help="Use the offline sensitivity model instead of the deployed client architecture")
    args = parser.parse_args()

    if args.rounds <= 0 or args.clients <= 0 or args.local_epochs <= 0 or args.runs <= 0:
        parser.error("--rounds, --clients, --local-epochs, and --runs must be greater than zero")
    if args.bcs_threshold < 0:
        parser.error("--bcs-threshold must be non-negative")

    print("=" * 70)
    print("  XFL / Federated Learning Benchmarks")
    print("  For: Research Paper — IoT Data Sharing with PQC + Blockchain + FL")
    print("=" * 70)

    print("  NOTE: This is an offline BCS/FedAvg simulation. The deployed FL system")
    print("  sends full weights and uses median aggregation; do not label this as a live-system measurement.\n")
    runs = [_run_once(args, args.seed + run_index) for run_index in range(args.runs)]
    primary = runs[0]
    xfl_results = primary["xfl"]
    fedavg_results = primary["fedavg"]

    # ── Communication volume summary ─────────────────────────────────────────
    banner("Section 2 — Per-Round Communication Volume Comparison")

    xfl_mean_bytes    = float(np.mean(xfl_results["bytes_per_round"]))
    fedavg_mean_bytes = float(np.mean(fedavg_results["bytes_per_round"]))
    reduction_pct     = (1.0 - xfl_mean_bytes / fedavg_mean_bytes) * 100.0 \
                        if fedavg_mean_bytes > 0 else 0.0
    avg_sparsity      = float(np.mean(xfl_results["sparsity_per_round"]))

    # Steady-state = last 50% of rounds (after BCS warmup where COO has overhead)
    warmup_cutoff = max(1, args.rounds // 2)
    xfl_ss_bytes      = float(np.mean(xfl_results["bytes_per_round"][warmup_cutoff:]))
    fedavg_ss_bytes   = float(np.mean(fedavg_results["bytes_per_round"][warmup_cutoff:]))
    ss_reduction_pct  = (1.0 - xfl_ss_bytes / fedavg_ss_bytes) * 100.0 \
                        if fedavg_ss_bytes > 0 else 0.0
    ss_sparsity       = float(np.mean(xfl_results["sparsity_per_round"][warmup_cutoff:]))

    print_table(
        headers=["Strategy", "Avg bytes/round (all)", "Avg bytes/round (steady-state)",
                 "Steady-state Reduction", "Steady-state Sparsity"],
        rows=[
            ["XFL (BCS)",
             f"{xfl_mean_bytes:,.0f}",
             f"{xfl_ss_bytes:,.0f}",
             f"{ss_reduction_pct:+.1f}%",
             f"{ss_sparsity:.1f}%"],
            ["FedAvg",
             f"{fedavg_mean_bytes:,.0f}",
             f"{fedavg_ss_bytes:,.0f}",
             "baseline",
             "0% (full weights)"],
        ],
        title="Communication Volume Comparison (bytes serialised per round, all clients)",
    )
    print(f"  Note: 'Steady-state' excludes first {warmup_cutoff} rounds. Report this result")
    print("  only when it is positive and consistently reproduced across runs.\n")

    # ── Convergence summary ──────────────────────────────────────────────────
    banner("Section 1 — Rounds to Convergence")

    xfl_losses    = [l for _, l in xfl_results["round_losses"]]
    fedavg_losses = [l for _, l in fedavg_results["round_losses"]]

    # Define "convergence" as the first round where loss drops below 1.1× final loss
    def rounds_to_converge(losses: list, tol: float = 0.05) -> int:
        """Round index where loss first reaches within tol of its minimum."""
        min_loss = min(losses)
        target   = min_loss * (1 + tol)
        for i, l in enumerate(losses):
            if l <= target:
                return i + 1
        return len(losses)

    xfl_conv    = rounds_to_converge(xfl_losses)
    fedavg_conv = rounds_to_converge(fedavg_losses)

    print_table(
        headers=["Strategy", "Final Loss", "Rounds to Converge (within 5% of min)", "Total Rounds"],
        rows=[
            ["XFL (BCS)", f"{xfl_losses[-1]:.5f}",    str(xfl_conv),    str(args.rounds)],
            ["FedAvg",    f"{fedavg_losses[-1]:.5f}",  str(fedavg_conv), str(args.rounds)],
        ],
        title="Convergence Summary",
    )

    # ── Save CSVs ────────────────────────────────────────────────────────────
    results_dir = ensure_results_dir()

    save_csv(
        "xfl_loss_curves.csv",
        ["run", "seed", "round", "xfl_loss", "fedavg_loss"],
        [[run_index + 1, result["seed"], r, f"{xl:.6f}", f"{fl:.6f}"]
         for run_index, result in enumerate(runs)
         for (r, xl), (_, fl) in zip(result["xfl"]["round_losses"], result["fedavg"]["round_losses"])],
    )

    save_csv(
        "xfl_communication.csv",
        ["run", "seed", "round", "xfl_bytes", "fedavg_bytes", "xfl_sparsity_pct"],
        [[run_index + 1, result["seed"], r + 1, result["xfl"]["bytes_per_round"][r],
          result["fedavg"]["bytes_per_round"][r], f"{result['xfl']['sparsity_per_round'][r]:.2f}"]
         for run_index, result in enumerate(runs) for r in range(args.rounds)],
    )

    save_csv(
        "xfl_summary.csv",
        ["metric", "xfl_bcs", "fedavg"],
        [
            ["avg_bytes_per_round_all",        f"{xfl_mean_bytes:.0f}",     f"{fedavg_mean_bytes:.0f}"],
            ["avg_bytes_per_round_steadystate", f"{xfl_ss_bytes:.0f}",      f"{fedavg_ss_bytes:.0f}"],
            ["ss_reduction_pct",               f"{ss_reduction_pct:.2f}",   "0.00"],
            ["avg_sparsity_pct_all",           f"{avg_sparsity:.2f}",        "0.00"],
            ["ss_sparsity_pct",                f"{ss_sparsity:.2f}",         "0.00"],
            ["final_loss",                     f"{xfl_losses[-1]:.6f}",     f"{fedavg_losses[-1]:.6f}"],
            ["rounds_to_converge",             str(xfl_conv),               str(fedavg_conv)],
            ["warmup_cutoff_rounds",           str(warmup_cutoff),          "0"],
            ["paired_runs",                     str(args.runs),              str(args.runs)],
            ["mean_reduction_pct_all",          f"{np.mean([r['reduction_pct'] for r in runs]):.2f}", "0.00"],
            ["stddev_reduction_pct_all",        f"{np.std([r['reduction_pct'] for r in runs]):.2f}", "0.00"],
        ],
    )

    save_metadata("xfl_bench_metadata.json", {
        "rounds": args.rounds, "clients": args.clients,
        "local_epochs": args.local_epochs, "bcs_threshold": args.bcs_threshold,
        "base_seed": args.seed, "runs": args.runs, "large_model": args.large_model,
    }, {"measurement_type": "offline_bcs_fedavg_simulation"})

    # ── Plot ─────────────────────────────────────────────────────────────────
    plot_results(xfl_results, fedavg_results, results_dir)

    print("=" * 70)
    print("  XFL benchmarks complete. Results in benchmarks/results/")
    print("=" * 70)


if __name__ == "__main__":
    main()

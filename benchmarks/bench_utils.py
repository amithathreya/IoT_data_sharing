"""
bench_utils.py — Shared utilities for all research-paper benchmark scripts.

Provides:
  - stats(samples)          → dict with mean, median, stddev, p95
  - print_table(headers, rows)  → formatted ASCII table to stdout
  - save_csv(path, headers, rows) → writes CSV to results/
  - ensure_results_dir()    → creates benchmarks/results/ if absent
"""

import os
import csv
import json
import numpy as np
import platform
import subprocess
import sys
from datetime import datetime

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def ensure_results_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    return RESULTS_DIR


def stats(samples: list) -> dict:
    """Return descriptive statistics for a list of numeric samples."""
    arr = np.array(samples, dtype=float)
    return {
        "mean":   float(np.mean(arr)),
        "median": float(np.median(arr)),
        "stddev": float(np.std(arr)),
        "p95":    float(np.percentile(arr, 95)),
        "min":    float(np.min(arr)),
        "max":    float(np.max(arr)),
        "n":      len(arr),
    }


def print_table(headers: list, rows: list, title: str = ""):
    """Pretty-print a table to stdout with fixed-width columns."""
    if title:
        print(f"\n{'─' * 70}")
        print(f"  {title}")
        print(f"{'─' * 70}")

    # Compute column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    fmt = "  " + "  ".join(f"{{:<{w}}}" for w in col_widths)
    sep = "  " + "  ".join("─" * w for w in col_widths)

    print(fmt.format(*headers))
    print(sep)
    for row in rows:
        print(fmt.format(*[str(c) for c in row]))
    print()


def save_csv(filename: str, headers: list, rows: list):
    """Write results to benchmarks/results/<filename>.csv"""
    ensure_results_dir()
    path = os.path.join(RESULTS_DIR, filename)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print(f"[bench_utils] Results saved → {path}")
    return path


def save_metadata(filename: str, parameters: dict, extra: dict = None):
    """Save reproducibility metadata next to a benchmark's result CSVs."""
    ensure_results_dir()
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=os.path.dirname(RESULTS_DIR), text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None

    payload = {
        "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "git_commit": commit,
        "python": sys.version,
        "platform": platform.platform(),
        "parameters": parameters,
    }
    if extra:
        payload.update(extra)

    path = os.path.join(RESULTS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    print(f"[bench_utils] Metadata saved → {path}")
    return path


def banner(text: str):
    """Print a section banner."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'═' * 70}")
    print(f"  [{ts}]  {text}")
    print(f"{'═' * 70}\n")

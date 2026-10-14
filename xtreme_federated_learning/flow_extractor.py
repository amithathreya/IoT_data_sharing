"""
flow_extractor.py — Lightweight Edge Network Flow Feature Extractor
=====================================================================
Converts raw IP packets into structured tabular network flow features
(compatible with CICIDS-2017 / TON_IoT benchmarks) without requiring
the heavy JVM/Java CICFlowMeter runtime.

Features Extracted (8 core features + 2 stats):
1. dst_port           - Target service/port (e.g. 22 SSH, 80 HTTP, 5671 AMQP)
2. flow_duration      - Duration of the bidirectional flow (seconds)
3. total_fwd_pkts     - Number of packets from source to destination
4. total_bwd_pkts     - Number of packets from destination to source
5. flow_bytes_per_sec - Total throughput (bytes / sec)
6. flow_pkts_per_sec  - Total packet rate (packets / sec)
7. flow_iat_mean      - Forward packet inter-arrival time mean (seconds)
8. bwd_iat_mean       - Backward packet inter-arrival time mean (seconds)
9. pkt_len_mean       - Average packet size across the flow (bytes)
10. pkt_len_std       - Packet size variation
"""

import time
import os
import collections
import threading
import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "dst_port",
    "flow_duration",
    "total_fwd_pkts",
    "total_bwd_pkts",
    "flow_bytes_per_sec",
    "flow_pkts_per_sec",
    "flow_iat_mean",
    "bwd_iat_mean",
    "pkt_len_mean",
    "pkt_len_std"
]

class EdgeFlowExtractor:
    def __init__(self, flow_timeout=3.0, max_active_flows=200, on_flow_callback=None):
        self.flow_timeout = flow_timeout
        self.max_active_flows = max_active_flows
        self.on_flow_callback = on_flow_callback
        self.active_flows = {}
        self.flow_buffer = collections.deque(maxlen=1000)
        self.lock = threading.Lock()
        self.running = False
        self._sniffer_thread = None

    def _get_flow_key(self, src_ip, dst_ip, sport, dport, proto):
        return (src_ip, dst_ip, sport, dport, proto)

    def process_packet_metadata(self, src_ip, dst_ip, sport, dport, proto, pkt_len, timestamp=None):
        """
        Record a packet into active flow tracking.
        Thread-safe. Can be fed from Scapy, raw sockets, or simulator.
        """
        now = timestamp if timestamp is not None else time.time()
        fkey = self._get_flow_key(src_ip, dst_ip, sport, dport, proto)
        rev_key = self._get_flow_key(dst_ip, src_ip, dport, sport, proto)

        with self.lock:
            if fkey in self.active_flows:
                flow = self.active_flows[fkey]
                flow["fwd_pkts"] += 1
                flow["fwd_bytes"] += pkt_len
                flow["pkt_lens"].append(pkt_len)
                flow["fwd_iats"].append(now - flow["last_seen"])
                flow["last_seen"] = now
            elif rev_key in self.active_flows:
                flow = self.active_flows[rev_key]
                flow["bwd_pkts"] += 1
                flow["bwd_bytes"] += pkt_len
                flow["pkt_lens"].append(pkt_len)
                flow["bwd_iats"].append(now - flow["last_seen"])
                flow["last_seen"] = now
            else:
                self.active_flows[fkey] = {
                    "start_time": now,
                    "last_seen": now,
                    "dst_port": dport,
                    "proto": proto,
                    "fwd_pkts": 1,
                    "bwd_pkts": 0,
                    "fwd_bytes": pkt_len,
                    "bwd_bytes": 0,
                    "pkt_lens": [pkt_len],
                    "fwd_iats": [],
                    "bwd_iats": [],
                }

            if len(self.active_flows) > self.max_active_flows:
                self._flush_expired(now)

    def _flush_expired(self, now):
        expired_keys = [k for k, v in self.active_flows.items() if (now - v["last_seen"]) >= self.flow_timeout]
        # Bound memory even during scans where many flows remain active.
        overflow = len(self.active_flows) - max(self.max_active_flows, 1)
        if overflow > 0:
            oldest = sorted(self.active_flows, key=lambda k: self.active_flows[k]["last_seen"])
            expired_keys.extend([k for k in oldest if k not in expired_keys][:overflow])
        completed = []
        for k in expired_keys:
            flow = self.active_flows.pop(k)
            record = self._flow_to_record(flow)
            if record is not None:
                self.flow_buffer.append(record)
                completed.append((k[0], record))

        # Immediately dispatch to real-time callback outside lock
        if self.on_flow_callback:
            for src_ip, rec in completed:
                try:
                    self.on_flow_callback(rec, src_ip=src_ip)
                except Exception:
                    pass

    def _flow_to_record(self, flow):
        duration = max(flow["last_seen"] - flow["start_time"], 0.0005)
        total_pkts = flow["fwd_pkts"] + flow["bwd_pkts"]
        total_bytes = flow["fwd_bytes"] + flow["bwd_bytes"]
        pkt_lens = flow["pkt_lens"]

        return {
            "dst_port": float(flow["dst_port"]),
            "flow_duration": float(duration),
            "total_fwd_pkts": float(flow["fwd_pkts"]),
            "total_bwd_pkts": float(flow["bwd_pkts"]),
            "flow_bytes_per_sec": float(total_bytes / duration),
            "flow_pkts_per_sec": float(total_pkts / duration),
            "flow_iat_mean": float(np.mean(flow["fwd_iats"])) if flow["fwd_iats"] else 0.0,
            "bwd_iat_mean": float(np.mean(flow["bwd_iats"])) if flow["bwd_iats"] else 0.0,
            "pkt_len_mean": float(np.mean(pkt_lens)) if pkt_lens else 0.0,
            "pkt_len_std": float(np.std(pkt_lens)) if len(pkt_lens) > 1 else 0.0,
        }

    def get_flow_snapshot(self, min_samples=10, flush_all=True):
        """
        Returns a Pandas DataFrame of recently completed flows.
        """
        with self.lock:
            if flush_all:
                now = time.time()
                for k in list(self.active_flows.keys()):
                    flow = self.active_flows.pop(k)
                    rec = self._flow_to_record(flow)
                    if rec is not None:
                        self.flow_buffer.append(rec)

            samples = list(self.flow_buffer)
            if len(samples) < min_samples:
                return pd.DataFrame(columns=FEATURE_COLUMNS)
            return pd.DataFrame(samples)[FEATURE_COLUMNS]

    def clear(self):
        with self.lock:
            self.active_flows.clear()
            self.flow_buffer.clear()

    def start_background_sniffer(self, iface="eth0"):
        """
        Starts a continuous background thread capturing network packets on the given interface.
        """
        try:
            from scapy.all import sniff, IP, TCP, UDP
        except ImportError:
            print("[FlowExtractor] Warning: Scapy not installed. Cannot start live packet sniffing.")
            return False

        self.running = True

        def _packet_handler(pkt):
            if not self.running or not pkt.haslayer(IP):
                return
            src_ip = pkt[IP].src
            dst_ip = pkt[IP].dst
            proto = pkt[IP].proto
            sport = pkt[TCP].sport if pkt.haslayer(TCP) else (pkt[UDP].sport if pkt.haslayer(UDP) else 0)
            dport = pkt[TCP].dport if pkt.haslayer(TCP) else (pkt[UDP].dport if pkt.haslayer(UDP) else 0)
            pkt_len = len(pkt)
            self.process_packet_metadata(src_ip, dst_ip, sport, dport, proto, pkt_len)

        def _sniff_worker():
            print(f"[FlowExtractor] Live background sniffer started on interface: {iface}")
            while self.running:
                try:
                    sniff(iface=iface, prn=_packet_handler, store=False, timeout=2.0)
                    with self.lock:
                        self._flush_expired(time.time())
                except Exception:
                    time.sleep(1.0)

        self._sniffer_thread = threading.Thread(target=_sniff_worker, daemon=True)
        self._sniffer_thread.start()
        return True

    def start_simulated_stream(self, interval=0.8, anomaly_chance=0.15):
        """
        Continuously generates background IoT traffic flows for headless testing or drills.
        """
        self.running = True

        def _sim_worker():
            print(f"[FlowExtractor] Continuous simulated flow stream started (Interval: {interval}s)...")
            while self.running:
                time.sleep(interval)
                synth = generate_synthetic_flows(num_samples=1, anomaly_ratio=1.0 if np.random.rand() < anomaly_chance else 0.0)
                rec = synth.iloc[0].to_dict()
                src_ip = "192.168.1.185" if rec.get("label", 0) == 1 else "192.168.1.50"
                with self.lock:
                    self.flow_buffer.append(rec)
                if self.on_flow_callback:
                    try:
                        self.on_flow_callback(rec, src_ip=src_ip)
                    except Exception:
                        pass

        self._sniffer_thread = threading.Thread(target=_sim_worker, daemon=True)
        self._sniffer_thread.start()
        return True

    def stop(self):
        self.running = False
        print("[FlowExtractor] Sniffer stopped.")

def generate_synthetic_flows(num_samples=100, anomaly_ratio=0.15, seed=42):
    """
    Generates realistic benign IoT flows and simulated network attacks
    (DDoS floods, port scans, and brute-force).
    Useful for training calibration, edge test drills, and local testing.
    """
    np.random.seed(seed)
    records = []
    num_anomalies = int(num_samples * anomaly_ratio)
    num_benign = num_samples - num_anomalies

    # 1. Benign IoT Flows (MQTT 1883, AMQP 5671, HTTP 80/443, NTP 123)
    benign_ports = [1883, 5671, 80, 443, 123, 8080]
    for _ in range(num_benign):
        dport = float(np.random.choice(benign_ports))
        duration = float(np.random.uniform(0.1, 5.0))
        fwd_pkts = float(np.random.randint(2, 25))
        bwd_pkts = float(np.random.randint(1, 20))
        mean_pkt_len = float(np.random.uniform(64, 400))
        total_bytes = (fwd_pkts + bwd_pkts) * mean_pkt_len
        total_pkts = fwd_pkts + bwd_pkts

        records.append({
            "dst_port": dport,
            "flow_duration": duration,
            "total_fwd_pkts": fwd_pkts,
            "total_bwd_pkts": bwd_pkts,
            "flow_bytes_per_sec": total_bytes / duration,
            "flow_pkts_per_sec": total_pkts / duration,
            "flow_iat_mean": float(np.random.uniform(0.05, 0.4)),
            "bwd_iat_mean": float(np.random.uniform(0.05, 0.4)),
            "pkt_len_mean": mean_pkt_len,
            "pkt_len_std": float(np.random.uniform(5, 50)),
            "label": 0  # Benign
        })

    # 2. Attack Flows (Floods, Port Scans, Brute Force)
    for _ in range(num_anomalies):
        attack_type = np.random.choice(["flood", "port_scan", "brute_force"])
        if attack_type == "flood":
            # UDP / SYN flood: massive packet rate, short duration, fixed payload
            duration = float(np.random.uniform(0.01, 0.5))
            fwd_pkts = float(np.random.randint(200, 2000))
            bwd_pkts = 0.0
            mean_pkt_len = float(np.random.uniform(1200, 1450))
            total_bytes = fwd_pkts * mean_pkt_len
            total_pkts = fwd_pkts
            dport = float(np.random.choice([9999, 80, 5671, 53]))
            iat = float(np.random.uniform(0.00001, 0.001))
            records.append({
                "dst_port": dport,
                "flow_duration": duration,
                "total_fwd_pkts": fwd_pkts,
                "total_bwd_pkts": bwd_pkts,
                "flow_bytes_per_sec": total_bytes / duration,
                "flow_pkts_per_sec": total_pkts / duration,
                "flow_iat_mean": iat,
                "bwd_iat_mean": 0.0,
                "pkt_len_mean": mean_pkt_len,
                "pkt_len_std": float(np.random.uniform(0.1, 5.0)),
                "label": 1  # Anomaly / Attack
            })
        elif attack_type == "port_scan":
            # Rapid single packet probes across ephemeral ports
            duration = float(np.random.uniform(0.001, 0.02))
            fwd_pkts = 1.0
            bwd_pkts = 0.0
            mean_pkt_len = float(np.random.uniform(40, 64))
            records.append({
                "dst_port": float(np.random.randint(1024, 65535)),
                "flow_duration": duration,
                "total_fwd_pkts": fwd_pkts,
                "total_bwd_pkts": bwd_pkts,
                "flow_bytes_per_sec": mean_pkt_len / duration,
                "flow_pkts_per_sec": fwd_pkts / duration,
                "flow_iat_mean": 0.0,
                "bwd_iat_mean": 0.0,
                "pkt_len_mean": mean_pkt_len,
                "pkt_len_std": 0.0,
                "label": 1
            })
        else: # brute force
            duration = float(np.random.uniform(0.2, 1.5))
            fwd_pkts = float(np.random.randint(15, 60))
            bwd_pkts = float(np.random.randint(10, 40))
            mean_pkt_len = float(np.random.uniform(80, 200))
            total_bytes = (fwd_pkts + bwd_pkts) * mean_pkt_len
            total_pkts = fwd_pkts + bwd_pkts
            records.append({
                "dst_port": float(np.random.choice([22, 5671, 80])),
                "flow_duration": duration,
                "total_fwd_pkts": fwd_pkts,
                "total_bwd_pkts": bwd_pkts,
                "flow_bytes_per_sec": total_bytes / duration,
                "flow_pkts_per_sec": total_pkts / duration,
                "flow_iat_mean": float(np.random.uniform(0.005, 0.02)),
                "bwd_iat_mean": float(np.random.uniform(0.005, 0.02)),
                "pkt_len_mean": mean_pkt_len,
                "pkt_len_std": float(np.random.uniform(10, 30)),
                "label": 1
            })

    df = pd.DataFrame(records).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return df

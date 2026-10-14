"""
edge_ids.py — Real-Time Edge Intrusion Detection & Mitigation Engine
====================================================================
Runs locally on Raspberry Pi / edge nodes. Uses a global federated XGBoost
ensemble to score live network flows, flag anomalies, and emit alerts.

Attack Signatures Detected:
- UDP / ICMP / SYN Floods (DoS/DDoS)
- Stealth Port Scans & Subnet Sweeps
- Brute-Force Attacks (SSH, AMQP, HTTP)
- Data Exfiltration / Unusual Outbound Bursts
"""

import os
import time
import json
import argparse
import numpy as np
from typing import Dict, Any, Optional

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

from flow_extractor import FEATURE_COLUMNS

class EdgeIntrusionDetector:
    def __init__(self, model_path: Optional[str] = None, threshold: float = 0.85):
        self.threshold = threshold
        self.bst = None
        self.boosters = []
        self.total_flows_inspected = 0
        self.total_intrusions_detected = 0

        # Model resolution order
        if model_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            candidates = [
                "/dev/shm/global_xgboost_model.json",
                os.path.join(base_dir, "global_xgboost_model.json"),
                "/dev/shm/local_xgboost_model.json",
                os.path.join(base_dir, "local_xgboost_model.json")
            ]
            for c in candidates:
                if os.path.exists(c):
                    model_path = c
                    break

        self.model_path = model_path
        self._load_model()

    def _load_model(self):
        if not XGB_AVAILABLE:
            print("[EdgeIDS] Warning: XGBoost is not available.")
            return

        if self.model_path and os.path.exists(self.model_path):
            try:
                with open(self.model_path, "r", encoding="utf-8") as model_file:
                    model = json.load(model_file)
                if model.get("format") == "xgb_probability_ensemble_v1":
                    if model.get("feature_columns") != FEATURE_COLUMNS or not model.get("models"):
                        raise ValueError("Invalid federated model feature schema or empty ensemble")
                    loaded = []
                    for member in model["models"]:
                        booster = xgb.Booster()
                        booster.load_model(bytearray(json.dumps(member["model_json"]).encode("utf-8")))
                        loaded.append(booster)
                    self.boosters = loaded
                    self.bst = None
                else:
                    self.bst = xgb.Booster()
                    self.bst.load_model(self.model_path)
                    self.boosters = [self.bst]
                print(f"[EdgeIDS] Loaded intrusion detection model from: {self.model_path}")
            except Exception as e:
                print(f"[EdgeIDS] Failed to load model: {e}")
                self.bst = None
        else:
            print("[EdgeIDS] No pre-trained model found yet. Engine in standby.")

    def inspect_flow(self, flow: Dict[str, float], src_ip: str = "Unknown") -> Dict[str, Any]:
        """
        Inspects a single tabular flow record.
        Execution Latency: < 1.0 ms on Raspberry Pi CPU.
        """
        self.total_flows_inspected += 1
        start_t = time.perf_counter()

        if self.bst is None and not self.boosters:
            self._load_model()
            if self.bst is None and not self.boosters:
                return {"is_intrusion": False, "anomaly_prob": 0.0, "category": "Model unavailable",
                        "latency_ms": (time.perf_counter() - start_t) * 1000.0,
                        "src_ip": src_ip, "dst_port": flow.get("dst_port", 0)}

        # Vectorize features strictly matching FEATURE_COLUMNS order
        vector = np.array([[flow.get(col, 0.0) for col in FEATURE_COLUMNS]], dtype=np.float32)
        dmatrix = xgb.DMatrix(vector, feature_names=FEATURE_COLUMNS)

        # Predict probability of malicious traffic
        prob = float(np.mean([booster.predict(dmatrix)[0] for booster in self.boosters]))
        latency_ms = (time.perf_counter() - start_t) * 1000.0

        is_intrusion = prob >= self.threshold
        attack_category = "Benign"

        if is_intrusion:
            self.total_intrusions_detected += 1
            attack_category = self._classify_attack(flow)
            self._emit_alert(src_ip, flow, prob, attack_category)

        return {
            "is_intrusion": is_intrusion,
            "anomaly_prob": prob,
            "category": attack_category,
            "latency_ms": latency_ms,
            "src_ip": src_ip,
            "dst_port": flow.get("dst_port", 0)
        }

    def _classify_attack(self, flow: Dict[str, float]) -> str:
        """
        Contextual attack classification based on flow behavior.
        """
        rate = flow.get("flow_pkts_per_sec", 0.0)
        bytes_sec = flow.get("flow_bytes_per_sec", 0.0)
        fwd_pkts = flow.get("total_fwd_pkts", 0.0)
        bwd_pkts = flow.get("total_bwd_pkts", 0.0)
        dport = int(flow.get("dst_port", 0))

        if rate > 250.0 or bytes_sec > 100_000.0:
            return "DDoS / High-Rate Packet Flood"
        elif fwd_pkts == 1.0 and bwd_pkts == 0.0 and rate > 50.0:
            return "Reconnaissance / Stealth Port Scan"
        elif dport in [22, 5671, 80, 443] and fwd_pkts > 20:
            return f"Brute Force / Service Exhaustion (Port {dport})"
        else:
            return "Protocol Anomaly / Outlier Telemetry"

    def _emit_alert(self, src_ip: str, flow: Dict[str, float], prob: float, category: str):
        """
        Emits an alert. Network blocking must be configured separately by an operator.
        """
        print(f"\n[!] [INTRUSION DETECTED - REVIEW REQUIRED]")
        print(f"    Source IP  : {src_ip}")
        print(f"    Target Port: {int(flow.get('dst_port', 0))}")
        print(f"    Category   : {category}")
        print(f"    Confidence : {prob * 100:.2f}%")
        print(f"    Telemetry  : Rate={flow.get('flow_pkts_per_sec', 0):.1f} pkts/s, "
              f"Bytes={flow.get('flow_bytes_per_sec', 0):.1f} B/s")

        # Optional Linux iptables mitigation (uncomment on live Pi):
        # if src_ip != "Unknown" and os.name == "posix":
        #     os.system(f"sudo iptables -A INPUT -s {src_ip} -j DROP")
        #     print(f"    [ACTION] Applied Linux iptables firewall rule dropping {src_ip}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect network flows with a local federated XGBoost model")
    parser.add_argument("--model", help="Global model JSON path")
    parser.add_argument("--interface", help="Capture interface (for example eth0 or wlan0)")
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--flow-timeout", type=float, default=3.0)
    args = parser.parse_args()
    detector = EdgeIntrusionDetector(model_path=args.model, threshold=args.threshold)
    if args.interface:
        from flow_extractor import EdgeFlowExtractor
        extractor = EdgeFlowExtractor(flow_timeout=args.flow_timeout,
                                      on_flow_callback=lambda flow, src_ip: detector.inspect_flow(flow, src_ip))
        if not extractor.start_background_sniffer(args.interface):
            raise SystemExit("Could not start packet capture; install scapy and grant capture permissions")
        print("[*] Live IDS running. Press Ctrl+C to stop. This reports alerts; it does not block traffic.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            extractor.stop()
            print(f"[*] Inspected {detector.total_flows_inspected} flows; detected {detector.total_intrusions_detected} alerts")
    else:
        print("[*] Pass --interface to inspect live traffic; no packet capture was started.")

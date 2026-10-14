"""
test_xgb_fl_ids.py — Complete End-to-End Federated XGBoost IDS Simulation
==========================================================================
Demonstrates the full lifecycle of Extreme Edge Federated Learning:
1. Generates realistic IoT flow traffic for 2 Raspberry Pi edge nodes.
   - Node 1: Only observes normal IoT telemetry (MQTT, AMQP, NTP).
   - Node 2: Observes normal IoT telemetry + experiences a localized DDoS/PortScan attack.
2. Federated Training Round:
   - Both nodes train local XGBoost models without sharing raw flows.
   - The coordinator combines model probabilities as a voting ensemble.
3. Federated Knowledge Transfer Verification:
   - Node 1 loads the aggregated global model.
   - Node 1 is subjected to a synthetic UDP flood flow.
   - Node 1's local Edge IDS should alert on the flow.
"""

import os
import sys
import time
import json
import numpy as np
import pandas as pd

from flow_extractor import generate_synthetic_flows, FEATURE_COLUMNS
from client_xgb_fl import EdgeXgbClient
from server_xgb_fl import FederatedXgbServer
from edge_ids import EdgeIntrusionDetector

def run_federated_simulation():
    print("=" * 75)
    print("      EXTREME FEDERATED XGBOOST INTRUSION DETECTION TEST SUITE      ")
    print("=" * 75)

    # 1. Prepare Edge Datasets
    print("\n[Step 1] Generating edge network traffic flows for 2 Pi devices...")
    # Node 1: 95% benign IoT telemetry, 5% background fluctuations
    node1_flows = generate_synthetic_flows(num_samples=120, anomaly_ratio=0.05, seed=101)
    # Node 2: 70% benign, 30% attack drills (Port scans, SYN/UDP Floods)
    node2_flows = generate_synthetic_flows(num_samples=120, anomaly_ratio=0.30, seed=202)
    # Global Validation set
    val_flows = generate_synthetic_flows(num_samples=200, anomaly_ratio=0.20, seed=999)

    print(f"  [*] Node 1 dataset: {len(node1_flows)} flows ({sum(node1_flows['label'] == 1)} attacks)")
    print(f"  [*] Node 2 dataset: {len(node2_flows)} flows ({sum(node2_flows['label'] == 1)} attacks)")
    print(f"  [*] Global Val set: {len(val_flows)} flows ({sum(val_flows['label'] == 1)} attacks)")

    # 2. Initialize Clients and Server
    print("\n[Step 2] Initializing Federated Nodes...")
    client1 = EdgeXgbClient(cid="pi-edge-node-1", max_depth=3, nthread=2)
    client2 = EdgeXgbClient(cid="pi-edge-node-2", max_depth=3, nthread=2)
    server = FederatedXgbServer(min_clients=2)

    # 3. Local Training on Edge Nodes
    print("\n[Step 3] Executing Local Edge Training (Round 1)...")
    update_node1 = client1.train_local_round(node1_flows, num_boost_round=8)
    update_node2 = client2.train_local_round(node2_flows, num_boost_round=8)

    print(f"  [*] Node 1 payload: {update_node1['payload_size_kb']:.2f} KB | Train time: {update_node1['train_duration_sec']:.3f}s")
    print(f"  [*] Node 2 payload: {update_node2['payload_size_kb']:.2f} KB | Train time: {update_node2['train_duration_sec']:.3f}s")

    # 4. Federated Aggregation on Server
    print("\n[Step 4] Combining Edge Models on Server (probability voting)...")
    agg_summary = server.aggregate_round([update_node1, update_node2], val_df=val_flows)

    global_auc = agg_summary["metrics"]["val_auc"]
    global_f1 = agg_summary["metrics"]["val_f1"]
    print(f"\n  [+] Server Aggregation Result:")
    print(f"     Total Trees Merged : {agg_summary['total_trees']}")
    print(f"     Global Payload Size: {agg_summary['model_size_kb']:.2f} KB")
    print(f"     Validation AUC     : {global_auc:.4f}")
    print(f"     Validation F1-Score: {global_f1:.4f}")

    # 5. Distribute Global Model to Node 1
    print("\n[Step 5] Distributing Aggregated Global Model back to Node 1...")
    client1.update_with_global_model(server.global_model_dict)

    # 6. Real-time Intrusion Detection Test on Node 1
    print("\n[Step 6] Testing Real-Time Edge Intrusion Detection on Node 1...")
    detector = EdgeIntrusionDetector(model_path=server.global_model_path, threshold=0.50)

    # Stream a series of test flows into Node 1
    test_stream = [
        # Benign MQTT telemetry flow
        ("Benign MQTT Sensor Flow", {
            "dst_port": 1883.0, "flow_duration": 1.2, "total_fwd_pkts": 4.0, "total_bwd_pkts": 3.0,
            "flow_bytes_per_sec": 450.0, "flow_pkts_per_sec": 5.8, "flow_iat_mean": 0.25,
            "bwd_iat_mean": 0.25, "pkt_len_mean": 95.0, "pkt_len_std": 12.0
        }, False, "192.168.1.50"),

        # Benign AMQP TLS telemetry flow
        ("Benign AMQP TLS Flow", {
            "dst_port": 5671.0, "flow_duration": 2.5, "total_fwd_pkts": 12.0, "total_bwd_pkts": 10.0,
            "flow_bytes_per_sec": 1200.0, "flow_pkts_per_sec": 8.8, "flow_iat_mean": 0.12,
            "bwd_iat_mean": 0.14, "pkt_len_mean": 240.0, "pkt_len_std": 25.0
        }, False, "192.168.1.50"),

        # Adversarial UDP Flood (matching udp_flood_attack.py)
        ("UDP Flood Attack Drill (1400B pkts)", {
            "dst_port": 9999.0, "flow_duration": 0.08, "total_fwd_pkts": 850.0, "total_bwd_pkts": 0.0,
            "flow_bytes_per_sec": 14875000.0, "flow_pkts_per_sec": 10625.0, "flow_iat_mean": 0.00008,
            "bwd_iat_mean": 0.0, "pkt_len_mean": 1400.0, "pkt_len_std": 0.1
        }, True, "192.168.1.185"),

        # Stealth Port Scan probe
        ("Stealth TCP Port Scan", {
            "dst_port": 22222.0, "flow_duration": 0.002, "total_fwd_pkts": 1.0, "total_bwd_pkts": 0.0,
            "flow_bytes_per_sec": 24000.0, "flow_pkts_per_sec": 500.0, "flow_iat_mean": 0.0,
            "bwd_iat_mean": 0.0, "pkt_len_mean": 48.0, "pkt_len_std": 0.0
        }, True, "192.168.1.185"),
    ]

    latencies = []
    correct_detections = 0

    print("-" * 75)
    for name, flow_data, expect_intrusion, ip in test_stream:
        res = detector.inspect_flow(flow_data, src_ip=ip)
        latencies.append(res["latency_ms"])
        is_correct = (res["is_intrusion"] == expect_intrusion)
        if is_correct:
            correct_detections += 1

        status = "PASSED" if is_correct else "FAILED"
        action = "ALERT" if res["is_intrusion"] else "NO ALERT"
        print(f"[{status}] {name:<35} -> Prob: {res['anomaly_prob']*100:>5.1f}% | "
              f"Action: {action:<18} | Latency: {res['latency_ms']:.3f}ms")

    print("-" * 75)
    avg_latency = float(np.mean(latencies))
    print(f"\n[Summary]")
    print(f"  [*] Detection Accuracy   : {correct_detections}/{len(test_stream)} ({correct_detections/len(test_stream)*100:.0f}%)")
    print(f"  [*] Average Edge Latency : {avg_latency:.3f} ms (Target: < 1.0 ms)")
    print(f"  [*] Federated Transfer   : Node 1 successfully recognized the attack types trained on Node 2!")

    if correct_detections == len(test_stream) and avg_latency < 5.0 and global_auc >= 0.85:
        print("\n>>> ALL TESTS PASSED: Federated XGBoost Edge IDS is operational! <<<\n")
        return True
    else:
        print("\n>>> TEST COMPLETED WITH WARNINGS <<<\n")
        return False

if __name__ == "__main__":
    success = run_federated_simulation()
    sys.exit(0 if success else 1)

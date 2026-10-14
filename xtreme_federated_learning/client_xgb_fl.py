"""
client_xgb_fl.py — Edge Federated XGBoost Client
=================================================
Ultra-lightweight Federated Learning client designed for Raspberry Pi & edge nodes.
Instead of heavy neural network backpropagation, this trains shallow gradient-boosted
decision trees on tabular network flow features.

Key Edge Optimizations:
- Memory: < 50 MB total RAM
- CPU usage: Constrained to 2 threads via 'nthread: 2'
- Tree method: 'hist' (histogram-based fast binning, optimal for ARM Cortex)
- Model size: 15-40 KB JSON payload (vs 10MB+ TensorFlow tensors)
- Communication: RabbitMQ AMQPS pinned to TLS 1.3 with ML-KEM/AES-GCM and ML-DSA envelopes.
"""

import os
import json
import time
import argparse
import numpy as np
import pandas as pd
from typing import Dict, Any

# Try importing ML libraries
try:
    import xgboost as xgb
    from sklearn.metrics import roc_auc_score, f1_score, precision_score, recall_score
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

from flow_extractor import FEATURE_COLUMNS, generate_synthetic_flows
from pqc_amqp import (GLOBAL_EXCHANGE, UPDATE_EXCHANGE, connect_broker,
                      load_kem_public_key, new_signer, open_broadcast_message,
                      pika, seal_message)

class EdgeXgbClient:
    def __init__(self, cid: str = "pi-node-1", max_depth: int = 3, nthread: int = 2):
        self.cid = cid
        self.max_depth = max_depth
        self.nthread = nthread
        self.bst = None
        self.round_number = 0
        self.kem_public_key = load_kem_public_key()
        self.signer, self.signer_public_key = new_signer()
        
        # Keep model artifacts beside the client so they survive a Pi reboot.
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_out = os.path.join(base_dir, f"local_model_{cid}.json")
        self.global_model_path = os.path.join(base_dir, "global_xgboost_model.json")

        self.params = {
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "max_depth": self.max_depth,
            "learning_rate": 0.2,
            "min_child_weight": 0.1,
            "tree_method": "hist",
            "subsample": 0.85,
            "colsample_bytree": 0.85,
            "nthread": self.nthread,
            "verbosity": 0
        }

    def train_local_round(self, df_flows: pd.DataFrame, num_boost_round: int = 5) -> Dict[str, Any]:
        """
        Trains local boosted trees on the edge device using extracted network flows.
        Returns a dictionary containing the serialized model, tree count, and metrics.
        """
        if not XGB_AVAILABLE:
            raise RuntimeError("XGBoost is not installed. Please run: pip install xgboost")

        missing = [col for col in FEATURE_COLUMNS + ["label"] if col not in df_flows]
        if missing:
            raise ValueError("Flow data is missing required columns: " + ", ".join(missing))
        if len(df_flows) < 4:
            raise ValueError("At least four labeled flows are required for local training")
        if df_flows["label"].nunique() < 2:
            raise ValueError("Local training requires both benign (0) and attack (1) labels")
        self.round_number += 1
        start_time = time.time()

        # Split features and labels
        X = df_flows[FEATURE_COLUMNS].to_numpy(dtype=np.float32)
        y = df_flows["label"].to_numpy(dtype=int)
        if not np.isfinite(X).all() or not np.isin(y, [0, 1]).all():
            raise ValueError("Features must be finite and labels must be binary 0/1")

        # 80/20 train/eval split
        rng = np.random.default_rng(self.round_number)
        order = rng.permutation(len(X))
        split_idx = min(max(int(len(X) * 0.8), 2), len(X) - 1)
        train_idx, val_idx = order[:split_idx], order[split_idx:]
        X_train, y_train = X[train_idx], y[train_idx]
        X_val, y_val = X[val_idx], y[val_idx]

        dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=FEATURE_COLUMNS)
        dval = xgb.DMatrix(X_val, label=y_val, feature_names=FEATURE_COLUMNS)

        # Train local trees
        self.bst = xgb.train(
            self.params,
            dtrain,
            num_boost_round=num_boost_round,
            evals=[(dval, "val")],
            verbose_eval=False
        )

        train_duration = time.time() - start_time

        # Validate local performance
        preds = self.bst.predict(dval)
        binary_preds = (preds >= 0.5).astype(int)

        auc = float(roc_auc_score(y_val, preds)) if len(np.unique(y_val)) > 1 else None
        f1 = float(f1_score(y_val, binary_preds, zero_division=0))
        prec = float(precision_score(y_val, binary_preds, zero_division=0))
        rec = float(recall_score(y_val, binary_preds, zero_division=0))

        # Dump model to JSON format (extremely compact for edge transport)
        self.bst.save_model(self.model_out)
        with open(self.model_out, "r", encoding="utf-8") as model_file:
            model_json_str = model_file.read()
        model_dict = json.loads(model_json_str)
        trees_count = len(model_dict.get("learner", {}).get("gradient_booster", {}).get("model", {}).get("trees", []))

        payload_bytes = model_json_str.encode("utf-8")
        payload_size_kb = len(payload_bytes) / 1024.0

        print(f"[Client {self.cid}] Round {self.round_number} complete in {train_duration:.3f}s. "
              f"Trees: {trees_count} | Payload: {payload_size_kb:.2f} KB | Val AUC: {auc:.4f} | F1: {f1:.4f}")

        return {
            "client_id": self.cid,
            "round": self.round_number,
            "num_samples": len(X_train),
            "feature_columns": FEATURE_COLUMNS,
            "num_trees": trees_count,
            "train_duration_sec": train_duration,
            "payload_size_kb": payload_size_kb,
            "model_json": model_dict,
            "metrics": {
                "auc": auc,
                "f1": f1,
                "precision": prec,
                "recall": rec
            }
        }

    def update_with_global_model(self, global_model_dict: Dict[str, Any]):
        """
        Receives aggregated global XGBoost model from the server
        and loads it for real-time local edge intrusion detection.
        """
        if not XGB_AVAILABLE:
            return

        global_json_str = json.dumps(global_model_dict)
        with open(self.global_model_path, "w", encoding="utf-8") as f:
            f.write(global_json_str)
        if global_model_dict.get("format") == "xgb_probability_ensemble_v1":
            # IDS owns prediction across all ensemble members; retain the artifact locally.
            if global_model_dict.get("feature_columns") != FEATURE_COLUMNS:
                raise ValueError("Global model feature schema does not match this client")
        else:
            # Backward-compatible loading for legacy single-booster files.
            self.bst = xgb.Booster()
            self.bst.load_model(bytearray(global_json_str.encode("utf-8")))
        print(f"[Client {self.cid}] Saved updated global model to {self.global_model_path}.")

    def start_messaging(self, update: Dict[str, Any]):
        """Publish a PQC-encrypted model update and listen for global models."""
        connection = connect_broker()
        channel = connection.channel()
        channel.exchange_declare(exchange=UPDATE_EXCHANGE, exchange_type="fanout", durable=True)
        channel.exchange_declare(exchange=GLOBAL_EXCHANGE, exchange_type="fanout", durable=True)
        queue = channel.queue_declare(queue="", exclusive=True).method.queue
        channel.queue_bind(exchange=GLOBAL_EXCHANGE, queue=queue)

        def on_global_model(ch, method, properties, body):
            try:
                model = json.loads(open_broadcast_message(body))
                self.update_with_global_model(model)
                print(f"[Client {self.cid}] Received and saved global round {model.get('round')}.")
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as exc:
                print(f"[Client {self.cid}] Rejected global model: {exc}")
                ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue=queue, on_message_callback=on_global_model)
        envelope = seal_message(json.dumps(update, separators=(",", ":")).encode("utf-8"),
                                self.kem_public_key, self.signer, self.signer_public_key)
        channel.basic_publish(
            exchange=UPDATE_EXCHANGE,
            routing_key="",
            body=envelope,
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
        print(f"[Client {self.cid}] Published encrypted model update; waiting for global model.")
        channel.start_consuming()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train an edge model on labeled flow CSV, then join a federation")
    parser.add_argument("--data", help="CSV containing FEATURE_COLUMNS and binary label (0 benign, 1 intrusion)")
    parser.add_argument("--client-id", default="pi-node-1")
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()
    client = EdgeXgbClient(cid=args.client_id)
    if args.data:
        flows = pd.read_csv(args.data)
    else:
        print("[*] No --data given; using synthetic flows for a local demo only.")
        flows = generate_synthetic_flows(num_samples=300, anomaly_ratio=0.2)
    update = client.train_local_round(flows, num_boost_round=args.rounds)
    print(f"[*] Local training complete: {update['num_samples']} training flows, {update['payload_size_kb']:.2f} KiB model")
    client.start_messaging(update)

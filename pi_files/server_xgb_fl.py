"""RabbitMQ coordinator for federated XGBoost flow classifiers."""

import json
import os
import tempfile
from typing import Any, Dict, List

import numpy as np
import pandas as pd

try:
    import xgboost as xgb
    from sklearn.metrics import (roc_auc_score, f1_score, precision_score,
                                 recall_score, confusion_matrix)
except ImportError as exc:
    xgb = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from flow_extractor import FEATURE_COLUMNS
from pqc_amqp import (GLOBAL_EXCHANGE, UPDATE_EXCHANGE, connect_broker,
                      load_kem_keys, new_signer, open_message, pika,
                      seal_broadcast_message)


def _load_booster(model: Dict[str, Any]) -> Any:
    booster = xgb.Booster()
    booster.load_model(bytearray(json.dumps(model).encode("utf-8")))
    return booster


class FederatedXgbServer:
    """Keep the latest model per node and distribute a probability-voting ensemble."""

    def __init__(self, min_clients: int = 2, model_path: str = None):
        if _IMPORT_ERROR:
            raise RuntimeError("Install xgboost, numpy, pandas, and scikit-learn") from _IMPORT_ERROR
        self.min_clients = max(1, int(min_clients))
        self.round_number = 0
        self.global_model_dict = None
        self.global_bst = None
        self.history = []
        self.client_updates: Dict[str, Dict[str, Any]] = {}
        self.kem_public_key, self.kem_private_key = load_kem_keys()
        self.signer, self.signer_public_key = new_signer()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.global_model_path = model_path or os.path.join(base_dir, "global_xgboost_model.json")
        self.connection = None
        self.channel = None

    def aggregate_round(self, client_updates: List[Dict[str, Any]],
                        val_df: pd.DataFrame = None) -> Dict[str, Any]:
        if not client_updates:
            raise ValueError("No client updates provided for aggregation")
        for update in client_updates:
            cid = str(update.get("client_id", "")).strip()
            if not cid or not isinstance(update.get("model_json"), dict):
                raise ValueError("Each update must include client_id and model_json")
            if update.get("feature_columns", FEATURE_COLUMNS) != FEATURE_COLUMNS:
                raise ValueError(f"Client {cid} has an incompatible feature schema")
            _load_booster(update["model_json"])
            self.client_updates[cid] = {
                "client_id": cid,
                "num_samples": max(0, int(update.get("num_samples", 0))),
                "model_json": update["model_json"],
                "feature_columns": FEATURE_COLUMNS,
            }

        self.round_number += 1
        members = list(self.client_updates.values())
        self.global_model_dict = {
            "format": "xgb_probability_ensemble_v1",
            "feature_columns": FEATURE_COLUMNS,
            "round": self.round_number,
            "models": [{k: v for k, v in member.items() if k != "feature_columns"}
                       for member in members],
        }
        serialized = json.dumps(self.global_model_dict, separators=(",", ":"))
        os.makedirs(os.path.dirname(os.path.abspath(self.global_model_path)), exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(
            prefix="global-xgb-", suffix=".json",
            dir=os.path.dirname(os.path.abspath(self.global_model_path)))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                out.write(serialized)
            os.replace(temporary_path, self.global_model_path)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)

        boosters = [_load_booster(member["model_json"]) for member in members]
        self.global_bst = boosters
        metrics = {}
        if val_df is not None and len(val_df):
            X_val = val_df[FEATURE_COLUMNS].to_numpy(dtype=np.float32)
            y_val = val_df["label"].to_numpy(dtype=int)
            dval = xgb.DMatrix(X_val, feature_names=FEATURE_COLUMNS)
            preds = np.mean([booster.predict(dval) for booster in boosters], axis=0)
            binary = (preds >= 0.5).astype(int)
            metrics = {
                "val_auc": float(roc_auc_score(y_val, preds)) if len(np.unique(y_val)) > 1 else None,
                "val_f1": float(f1_score(y_val, binary, zero_division=0)),
                "val_precision": float(precision_score(y_val, binary, zero_division=0)),
                "val_recall": float(recall_score(y_val, binary, zero_division=0)),
            }
            if len(np.unique(y_val)) > 1:
                tn, fp, fn, tp = confusion_matrix(y_val, binary, labels=[0, 1]).ravel()
                metrics.update(tp=int(tp), fp=int(fp), tn=int(tn), fn=int(fn))

        summary = {
            "round": self.round_number,
            "participating_clients": len(client_updates),
            "ensemble_clients": len(members),
            "total_samples": sum(int(u.get("num_samples", 0)) for u in client_updates),
            "total_trees": sum(len(b.get_dump()) for b in boosters),
            "model_size_kb": len(serialized.encode("utf-8")) / 1024.0,
            "metrics": metrics,
        }
        self.history.append(summary)
        return summary

    def _on_client_update(self, channel, method, properties, body):
        try:
            payload = json.loads(open_message(body, self.kem_private_key))
            cid = str(payload["client_id"])
            if payload.get("feature_columns") != FEATURE_COLUMNS:
                raise ValueError("Client feature schema does not match coordinator")
            self.client_updates[cid] = payload
            print(f"[Coordinator] Received encrypted model update from {cid} "
                  f"({len(self.client_updates)}/{self.min_clients} clients)")
            if len(self.client_updates) >= self.min_clients:
                summary = self.aggregate_round(list(self.client_updates.values()))
                self._publish_global_model()
                print(f"[Coordinator] Round {summary['round']} published: "
                      f"{summary['ensemble_clients']} client models, "
                      f"{summary['model_size_kb']:.1f} KiB")
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as exc:
            print(f"[Coordinator] Rejected model update: {exc}")
            channel.basic_ack(delivery_tag=method.delivery_tag)

    def _publish_global_model(self):
        body = json.dumps(self.global_model_dict, separators=(",", ":")).encode("utf-8")
        envelope = seal_broadcast_message(body, self.signer, self.signer_public_key)
        self.channel.basic_publish(
            exchange=GLOBAL_EXCHANGE,
            routing_key="",
            body=envelope,
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )

    def serve(self):
        print("[Coordinator] Connecting to RabbitMQ over TLS 1.3...")
        self.connection = connect_broker()
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange=UPDATE_EXCHANGE, exchange_type="fanout", durable=True)
        self.channel.exchange_declare(exchange=GLOBAL_EXCHANGE, exchange_type="fanout", durable=True)
        self.channel.basic_qos(prefetch_count=1)
        queue = self.channel.queue_declare(queue="", exclusive=True).method.queue
        self.channel.queue_bind(exchange=UPDATE_EXCHANGE, queue=queue)
        self.channel.basic_consume(queue=queue, on_message_callback=self._on_client_update)
        print(f"[Coordinator] Waiting for encrypted XGBoost updates; min clients={self.min_clients}")
        self.channel.start_consuming()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the TLS/PQC XGBoost coordinator")
    parser.add_argument("--min-clients", type=int, default=2)
    args = parser.parse_args()
    FederatedXgbServer(min_clients=args.min_clients).serve()

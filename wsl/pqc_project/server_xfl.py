import json
import time
import hashlib
import numpy as np
import flwr as fl
from typing import List, Tuple, Dict
from flwr.common import Scalar, parameters_to_ndarrays, ndarrays_to_parameters
from web3 import Web3
from eth_account import Account

BESU_RPC    = "http://localhost:8545"
PRIVATE_KEY = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"

w3 = Web3(Web3.HTTPProvider(BESU_RPC))
account = Account.from_key(PRIVATE_KEY)

with open("/home/amith/pqc_project/blockchain/contract.json") as f:
    contract_info = json.load(f)
contract = w3.eth.contract(address=contract_info["address"], abi=contract_info["abi"])

def weighted_average(metrics: List[Tuple[int, Dict[str, Scalar]]]) -> Dict[str, Scalar]:
    total_examples = sum(num_examples for num_examples, _ in metrics)
    if total_examples == 0: return {"accuracy": 0}
    accuracy = sum(num_examples * m.get("accuracy", 0) for num_examples, m in metrics) / total_examples
    return {"accuracy": accuracy}

class IntegratedLayerWiseStrategy(fl.server.strategy.FedAvg):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.global_weights = None
        self.layer_slices = {
            0: (0, 3), 1: (3, 6), 2: (6, 9), 3: (9, 11)
        }

    def aggregate_fit(self, server_round, results, failures):
        aggregated_parameters, metrics = super().aggregate_fit(server_round, results, failures)

        if aggregated_parameters is not None:
            param_bytes = str(aggregated_parameters).encode()
            model_hash = hashlib.sha256(param_bytes).digest()
            try:
                tx = contract.functions.storeRecord(
                    f"FL-Round-{server_round}", model_hash, int(time.time())
                ).build_transaction({
                    "from": account.address,
                    "nonce": w3.eth.get_transaction_count(account.address),
                    "gas": 200000, "gasPrice": 0
                })
                signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                print(f"⛓️ [Besu Audit] Logged FL Round {server_round} | Hash: {tx_hash.hex()[:10]}...")
            except Exception as e:
                print(f"⛓️ [Besu Audit Error]: {e}")

        return aggregated_parameters, metrics

def main():
    strategy = IntegratedLayerWiseStrategy(
        fraction_fit=1.0,
        min_evaluate_clients=1,
        min_fit_clients=1,
        min_available_clients=1,
        evaluate_metrics_aggregation_fn=weighted_average,
    )
    fl.server.start_server(
        # CHANGED THIS LINE TO FIX THE TCP HANDSHAKE CRASH
        server_address="0.0.0.0:50051",
        config=fl.server.ServerConfig(num_rounds=9999999999),
        strategy=strategy
    )

if __name__ == "__main__":
    main()

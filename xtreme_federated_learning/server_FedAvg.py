import flwr as fl
from typing import List, Tuple, Dict, Optional
from flwr.common import Scalar

def weighted_average(metrics: List[Tuple[int, Dict[str, Scalar]]]) -> Dict[str, Scalar]:
    accuracies = [num_examples * m["accuracy"] for num_examples, m in metrics]
    examples = [num_examples for num_examples, _ in metrics]

    return {"accuracy": sum(accuracies) / sum(examples)}
def main():
    strategy = fl.server.strategy.FedAvg(
        fraction_fit=1,  
        fraction_evaluate=1, 
        min_fit_clients=8, 
        min_evaluate_clients=8,
        min_available_clients=8,
        evaluate_metrics_aggregation_fn=weighted_average,
    )

    fl.server.start_server(
        server_address="0.0.0.0:8080",
        config=fl.server.ServerConfig(num_rounds=20),  
        strategy=strategy,  
    )

if __name__ == "__main__":
    main()

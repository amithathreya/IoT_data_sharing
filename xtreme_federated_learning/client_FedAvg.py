import flwr as fl
import tensorflow as tf
import numpy as np
import os
import json
import time
import psutil
import pandas as pd
from sklearn.preprocessing import StandardScaler

def load_client_data(client_id):
    client_dir = f"client_{client_id}"
    
    x_train = pd.read_csv(os.path.join(client_dir, "X_train.csv")).values
    y_train = pd.read_csv(os.path.join(client_dir, "y_train.csv")).values
    
    x_test = pd.read_csv(os.path.join(client_dir, "X_test.csv")).values
    y_test = pd.read_csv(os.path.join(client_dir, "y_test.csv")).values
    
    return x_train, y_train, x_test, y_test

def get_model(input_shape ):
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001)

    model = tf.keras.models.Sequential([
        tf.keras.layers.Dense(256, activation="relu", input_shape=input_shape),
        tf.keras.layers.Dense(128, activation="relu"),
        tf.keras.layers.Dense(9, activation="softmax")
    ])
    
    model.compile(optimizer=optimizer, loss="categorical_crossentropy", metrics=["accuracy"])
    return model

class FlowerClient(fl.client.NumPyClient):
    def __init__(self, node_rank):
        self.model = get_model((20,))  # 20 features
        self.node_rank = node_rank
        self.x_train, self.y_train, self.x_test, self.y_test = load_client_data(node_rank)
        self.history = {"rounds": []}

    def get_parameters(self, config):
        return self.model.get_weights()

    def fit(self, parameters, config):
        self.model.set_weights(parameters)

        start_time = time.time()
        energy_before = ina.power() if ina else None

        history = self.model.fit(
            self.x_train, 
            self.y_train, 
            epochs=10, 
            batch_size=64, 
            verbose=1,
            validation_data=(self.x_test, self.y_test)
        )

        train_time = time.time() - start_time
        energy_after = ina.power() if ina else None
        energy_consumed = (energy_after - energy_before) if (ina and energy_before) else None

        round_metrics = {
            "round": len(self.history["rounds"]) + 1,
            "train_loss": history.history["loss"][-1],
            "train_accuracy": history.history["accuracy"][-1],
            "val_loss": history.history["val_loss"][-1],
            "val_accuracy": history.history["val_accuracy"][-1],
            "train_time": train_time,
            "cpu_usage": psutil.cpu_percent(),
            "ram_usage": psutil.virtual_memory().percent,
            "energy_consumed_mW": energy_consumed,
            "network_sent_MB": psutil.net_io_counters().bytes_sent / (1024 * 1024),
            "network_received_MB": psutil.net_io_counters().bytes_recv / (1024 * 1024),
            "model_size_MB": sum([param.nbytes for param in self.model.get_weights()]) / (1024 * 1024),
        }

        self.history["rounds"].append(round_metrics)
        self.save_training_history()
        return self.model.get_weights(), len(self.x_train), {}

    def evaluate(self, parameters, config):
        self.model.set_weights(parameters)

        start_time = time.time()
        loss, accuracy = self.model.evaluate(self.x_test, self.y_test, verbose=0)
        eval_time = time.time() - start_time

        if self.history["rounds"]: 
            self.history["rounds"][-1]["test_loss"] = loss
            self.history["rounds"][-1]["test_accuracy"] = accuracy
            self.history["rounds"][-1]["eval_time"] = eval_time
            self.save_training_history()

        return loss, len(self.x_test), {"accuracy": accuracy}

    def save_training_history(self):
        """Sauvegarde l'historique en JSON."""
        history_file = f"client_{self.node_rank}_{self.model_type}_history.json"
        with open(history_file, "w") as f:
            json.dump(self.history, f, indent=4)
        print(f"Historique sauvegardé dans {history_file}")


if __name__ == "__main__":
    node_rank = int(input("Enter your client rank (0 for Client 1, 1 for Client 2, etc.): "))
    
    client = FlowerClient(node_rank)
    fl.client.start_numpy_client(server_address="192.168.1.129:8080", client=client)
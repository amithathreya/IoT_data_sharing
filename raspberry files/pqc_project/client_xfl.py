import os
import time
import psutil
import pandas as pd
import numpy as np
import tensorflow as tf
import flwr as fl

SERVER_ADDRESS = "192.168.29.73:8080"
FEATURE_DIM    = 20
LOCAL_DATA_LOG = "/home/test_pi/sensor_log.csv"

def get_model(input_shape=(20,)):
    model = tf.keras.models.Sequential([
        tf.keras.layers.Reshape((1, input_shape[0]), input_shape=input_shape),
        tf.keras.layers.SimpleRNN(256, return_sequences=True, name="rnn_1"),
        tf.keras.layers.SimpleRNN(128, return_sequences=True, name="rnn_2"),
        tf.keras.layers.SimpleRNN(64, name="rnn_3"),
        tf.keras.layers.Dense(9, activation="softmax", name="output")
    ])
    model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
    return model

def load_local_training_data():
    if not os.path.exists(LOCAL_DATA_LOG):
        return np.random.rand(10, FEATURE_DIM), tf.keras.utils.to_categorical(np.zeros(10), 9)

    df = pd.read_csv(LOCAL_DATA_LOG)
    x_train, y_train = [], []
    
    for i in range(len(df)):
        features = np.zeros(FEATURE_DIM)
        features[0] = df.iloc[i]['temperature']
        features[1] = df.iloc[i]['humidity']
        x_train.append(features)
        y_train.append(0)

    return np.array(x_train), tf.keras.utils.to_categorical(np.array(y_train), num_classes=9)

class LayerWiseRNNClient(fl.client.NumPyClient):
    def __init__(self, cid):
        self.cid = cid
        self.model = get_model((FEATURE_DIM,))
        self.layer_map = {
            0: ("rnn_1", 0, 3), 1: ("rnn_2", 3, 6),
            2: ("rnn_3", 6, 9), 3: ("output", 9, 11)
        }

    def get_parameters(self, config):
        return self.model.get_weights()

    def fit(self, parameters, config):
        self.model.set_weights(parameters)
        x_train, y_train = load_local_training_data()

        server_round = config.get("server_round", 0)
        layer_index = (server_round + self.cid) % len(self.layer_map)
        layer_name, start, end = self.layer_map[layer_index]

        print(f"\n[Node {self.cid}] Round {server_round} | Training Layer: {layer_name}")
        
        self.model.fit(x_train, y_train, epochs=5, batch_size=32, verbose=0)
        updated_params = self.model.get_weights()[start:end]
        
        return updated_params, len(x_train), {"layer_name": layer_name, "layer_index": layer_index}

    def evaluate(self, parameters, config):
        return 0.0, 0, {"accuracy": 0.0}

if __name__ == "__main__":
    cid = int(input("Enter node ID (e.g., 0): "))
    fl.client.start_numpy_client(server_address=SERVER_ADDRESS, client=LayerWiseRNNClient(cid))

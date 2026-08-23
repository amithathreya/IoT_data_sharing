import numpy as np
import tensorflow as tf
import collections
from client_xfl import get_model

def simulate_data_stream():
    np.random.seed(42)
    stream = []
    
    # 1. Warmup (Normal traffic, ~100KB to 1MB)
    for _ in range(50):
        sent = np.random.uniform(1e5, 1e6)
        recv = np.random.uniform(1e5, 1e6)
        stream.append([sent, recv])
        
    # 2. Gradual Drift (Slowly increasing to ~10MB over 100 samples)
    s_base = 1e6
    r_base = 1e6
    for i in range(100):
        s_base += 90000  # reaches ~10M
        r_base += 90000
        sent = s_base + np.random.uniform(-1e4, 1e4)
        recv = r_base + np.random.uniform(-1e4, 1e4)
        stream.append([sent, recv])
        
    # 3. Sudden Adversarial Spike (DDoS, Jump to ~1GB)
    for _ in range(10):
        sent = np.random.uniform(5e8, 1e9)
        recv = np.random.uniform(5e8, 1e9)
        stream.append([sent, recv])
        
    return stream

def run_test():
    print("Initializing test harness...")
    model = get_model()
    
    loss_fn = tf.keras.losses.MeanSquaredError()
    
    threshold_history = collections.deque(maxlen=100)
    k = 3.0
    
    stream = simulate_data_stream()
    
    buffer = []
    anomalies_flagged = 0
    drift_alarms = 0
    
    print("Processing stream...")
    for idx, (sent, recv) in enumerate(stream):
        scaled_sent = np.log1p(sent) / 10.0
        scaled_recv = np.log1p(recv) / 10.0
        
        buffer.extend([scaled_sent, scaled_recv])
        if len(buffer) > 20:
            buffer = buffer[-20:]
            
        if len(buffer) == 20:
            x_batch = np.array(buffer).reshape(1, 20)
            
            reconstruction = model(x_batch, training=False)
            anomaly_score = float(loss_fn(x_batch, reconstruction))
            
            if len(threshold_history) > 10:
                mu_loss = np.mean(threshold_history)
                sigma_loss = np.std(threshold_history)
                dynamic_threshold = mu_loss + (k * sigma_loss)
            else:
                dynamic_threshold = 10.0
                
            is_anomaly = anomaly_score >= dynamic_threshold
            
            if is_anomaly:
                if idx < 150:
                    drift_alarms += 1
                    print(f" [!] FALSE ALARM during warmup/drift at {idx} (Score: {anomaly_score:.4f} >= {dynamic_threshold:.4f})")
                else:
                    anomalies_flagged += 1
                    print(f" [*] TRUE ANOMALY caught at spike {idx} (Score: {anomaly_score:.4f} >= {dynamic_threshold:.4f})")
            else:
                # Normal or Gradual Drift: Update threshold history and train
                threshold_history.append(anomaly_score)
                with tf.GradientTape() as tape:
                    rec_train = model(x_batch, training=True)
                    loss_value = loss_fn(x_batch, rec_train)
                grads = tape.gradient(loss_value, model.trainable_weights)
                model.optimizer.apply_gradients(zip(grads, model.trainable_weights))
                
    print("\n--- Test Results ---")
    print(f"False Alarms during Gradual Drift (Target: ~0): {drift_alarms}")
    print(f"True Anomalies during Sudden Spike (Target: >0): {anomalies_flagged}")
    if anomalies_flagged > 0 and drift_alarms < 10:
        print("=> TEST PASSED: Adaptive threshold handles drift and catches spikes.")
    else:
        print("=> TEST FAILED.")

if __name__ == '__main__':
    run_test()

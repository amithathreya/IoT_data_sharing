import numpy as np
import tensorflow as tf
import collections
from client_xfl import get_model

def simulate_data_stream():
    np.random.seed(42)
    stream = []
    
    # 1. Warmup (Normal, ~29C, ~60%)
    for _ in range(50):
        t = 29.0 + np.random.uniform(-1, 1)
        h = 60.0 + np.random.uniform(-2, 2)
        stream.append([t, h])
        
    # 2. Gradual Drift (Slowly increasing to ~35C, ~70% over 100 samples)
    t_base = 29.0
    h_base = 60.0
    for i in range(100):
        t_base += 0.06
        h_base += 0.1
        t = t_base + np.random.uniform(-1, 1)
        h = h_base + np.random.uniform(-2, 2)
        stream.append([t, h])
        
    # 3. Sudden Adversarial Spike (Jump to 80C, 90%)
    for _ in range(10):
        t = 80.0 + np.random.uniform(-2, 2)
        h = 90.0 + np.random.uniform(-2, 2)
        stream.append([t, h])
        
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
    for idx, (t, h) in enumerate(stream):
        buffer.extend([t, h])
        if len(buffer) > 20:
            buffer = buffer[-20:]
            
        if len(buffer) == 20:
            x_batch = (np.array(buffer) / 100.0).reshape(1, 20)
            
            reconstruction = model(x_batch, training=False)
            anomaly_score = float(loss_fn(x_batch, reconstruction))
            
            if len(threshold_history) > 10:
                mu_loss = np.mean(threshold_history)
                sigma_loss = np.std(threshold_history)
                dynamic_threshold = mu_loss + (k * sigma_loss)
            else:
                dynamic_threshold = 1.0
                
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

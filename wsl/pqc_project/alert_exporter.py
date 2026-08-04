import pika
import json
import time
from prometheus_client import start_http_server, Counter, Gauge

# ── Configuration ──────────────────────────────────────────────
RABBITMQ_HOST = "127.0.0.1"
AMQP_USER     = "pqc_user"
AMQP_PASSWORD = "pqc_password"
EXPORTER_PORT = 8001

# ── Prometheus Metrics Definition ──────────────────────────────
# Counter: Tracks the total number of threats detected over time
THREAT_COUNTER = Counter(
    'iot_security_threats_total',
    'Total number of security anomalies detected',
    ['node_id', 'threat_class']
)

# Gauge: Tracks the confidence level of the most recent threat
THREAT_CONFIDENCE = Gauge(
    'iot_security_threat_confidence',
    'Confidence percentage of the latest threat',
    ['node_id']
)

# Gauge: Tracks the sensor values during the anomaly
ANOMALY_TEMP = Gauge('iot_security_anomaly_temperature', 'Temperature during threat', ['node_id'])
ANOMALY_HUM = Gauge('iot_security_anomaly_humidity', 'Humidity during threat', ['node_id'])

# ── RabbitMQ Consumer ──────────────────────────────────────────
def on_alert_received(ch, method, properties, body):
    alert_data = json.loads(body)
    node = str(alert_data['node_id'])
    threat_class = str(alert_data['threat_class'])

    print(f"🚨 [Exporter] Metric Updated for Node {node} | Class: {threat_class}")

    # Update Prometheus Metrics
    THREAT_COUNTER.labels(node_id=node, threat_class=threat_class).inc()
    THREAT_CONFIDENCE.labels(node_id=node).set(alert_data['confidence'] * 100)
    ANOMALY_TEMP.labels(node_id=node).set(alert_data['temperature'])
    ANOMALY_HUM.labels(node_id=node).set(alert_data['humidity'])

    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_rabbitmq_listener():
    credentials = pika.PlainCredentials(AMQP_USER, AMQP_PASSWORD)
    conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
    channel = conn.channel()

    channel.queue_declare(queue='security_alerts')
    channel.basic_consume(queue='security_alerts', on_message_callback=on_alert_received)

    print("[Exporter] Listening for RabbitMQ alerts...")

    # Robust connection loop
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        conn.close()

if __name__ == "__main__":
    # Start the Prometheus HTTP server on port 8001
    print(f"📈 [Exporter] Starting Prometheus metrics server on port {EXPORTER_PORT}")
    start_http_server(EXPORTER_PORT)

    # Start listening to RabbitMQ
    start_rabbitmq_listener()

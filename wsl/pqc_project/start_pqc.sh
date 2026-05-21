#!/bin/bash
echo "[*] Starting RabbitMQ..."
sudo systemctl start rabbitmq-server
sleep 2

echo "[*] Starting nginx..."
sudo pkill -9 nginx 2>/dev/null
sleep 1
/usr/local/nginx/sbin/nginx

echo "[*] Verifying..."
sudo systemctl status rabbitmq-server | grep Active
ss -tlnp | grep 5671

echo "[*] Done. Ready for Pi publisher."

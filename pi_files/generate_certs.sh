#!/bin/bash
set -e

# 1. Create a clean directory structure
mkdir -p certs
cd certs

echo "Generating Certificates..."

# 2. Generate Certificate Authority (CA) Keys
openssl req -new -x509 -days 3650 \
  -nodes -newkey rsa:4096 \
  -keyout ca_key.pem \
  -out ca_certificate.pem \
  -subj "/CN=MyRabbitMQ-CA"

# 3. Generate Client Private Key and CSR (Certificate Signing Request)
openssl req -new -nodes -newkey rsa:2048 \
  -keyout client_key.pem \
  -out client_req.pem \
  -subj "/CN=RaspberryPiClient"

# 4. Sign Client Certificate using the CA
openssl x509 -req -days 3650 \
  -in client_req.pem \
  -CA ca_certificate.pem \
  -CAkey ca_key.pem \
  -CAcreateserial \
  -out client_certificate.pem

# 5. Generate Server Private Key and CSR
openssl req -new -nodes -newkey rsa:2048 \
  -keyout server_key.pem \
  -out server_req.pem \
  -subj "/CN=rabbitmq-server"

# 6. Create extfile to specify Server IP addresses/Hostnames (Crucial for TLS validation)
# REPLACE 192.168.1.50 with your actual Server PC local network IP address
echo "subjectAltName = DNS:localhost, DNS:*, DNS:*.local, IP:127.0.0.1" > extfile.cnf

# 7. Sign Server Certificate using the CA
openssl x509 -req -days 3650 \
  -in server_req.pem \
  -CA ca_certificate.pem \
  -CAkey ca_key.pem \
  -CAcreateserial \
  -extfile extfile.cnf \
  -out server_certificate.pem

# 8. Clean up temporary request files
rm -f client_req.pem server_req.pem extfile.cnf ca_certificate.srl

echo "All certificates generated successfully in the './certs' directory!"


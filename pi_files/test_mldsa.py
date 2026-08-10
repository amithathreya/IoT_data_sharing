import oqs

message = b"Hello from Raspberry Pi - PQC test message"

with open("keys/publisher_mldsa_private.key", "rb") as f:
    private_key = f.read()

with oqs.Signature("ML-DSA-65", secret_key=private_key) as signer:
    signature = signer.sign(message)

with open("signed_message.bin", "wb") as f:
    f.write(message)

with open("signature.bin", "wb") as f:
    f.write(signature)

print("Message signed successfully.")
print("Signature length:", len(signature), "bytes")

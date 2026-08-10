# keygen.py (Run this on Windows)
import oqs, os

# Create certs folder if it doesn't exist
os.makedirs("certs", exist_ok=True)

with oqs.KeyEncapsulation("ML-KEM-768") as kem:
    pub_key = kem.generate_keypair()
    priv_key = kem.export_secret_key()
    
    # Save Public key for the Pi
    with open(os.path.join("certs", "server_kem_pub.key"), "wb") as f: 
        f.write(pub_key)
        
    # Save Private key for the Windows Server
    with open(os.path.join("certs", "consumer_kem_priv.key"), "wb") as f: 
        f.write(priv_key)
        
print("Keys generated successfully!")   
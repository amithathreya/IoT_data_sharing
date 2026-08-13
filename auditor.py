import json
import hashlib
from web3 import Web3

# ── Configuration ───────────────────────────────────────────
BESU_RPC = "http://127.0.0.1:8545"

print("==================================================")
print(" 🕵️  MILITARY IoT - BLOCKCHAIN DATA AUDITOR")
print("==================================================\n")

w3 = Web3(Web3.HTTPProvider(BESU_RPC))
if not w3.is_connected():
    print("❌ Cannot connect to Blockchain.")
    exit(1)

# Load Contract
try:
    with open("contract_address.txt", "r") as f:
        contract_address = f.read().strip()
    with open("contract_abi.json", "r") as f:
        contract_abi = json.load(f)
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)
except Exception:
    print("❌ Missing contract files. Run deploy.py first.")
    exit(1)


def audit_telemetry(node_id, temperature, humidity, timestamp_ns):
    """
    Takes plain-text data from a database (like Grafana), re-hashes it, 
    and checks if that exact hash exists immutably on the blockchain.
    """
    print(f"[{node_id}] Auditing Data: Temp={temperature}, Hum={humidity}, TS={timestamp_ns}")
    
    # 1. Reconstruct the JSON payload exactly as server.py did
    data = {
        "node_id": node_id,
        "temperature": temperature,
        "humidity": humidity,
        "timestamp_ns": timestamp_ns
    }
    
    # 2. Compute the SHA-256 Hash
    payload_str = json.dumps(data, sort_keys=True).encode('utf-8')
    computed_hash_bytes = hashlib.sha256(payload_str).digest()
    computed_hash_hex = w3.to_hex(computed_hash_bytes)
    
    print(f" └─ 🔍 Computed Fingerprint : {computed_hash_hex}")
    print(" └─ ⏳ Scanning immutable ledger for matching fingerprint...")

    # 3. Query the blockchain for matching events
    events = contract.events.TelemetryRecorded.create_filter(from_block=0).get_all_entries()
    
    for event in events:
        recorded_hash = w3.to_hex(event.args.payloadHash)
        if recorded_hash == computed_hash_hex:
            print(f" └─ ✅ INTEGRITY VERIFIED! Cryptographic match found in Block #{event.blockNumber}\n")
            return True
            
    print(" └─ ❌ INTEGRITY COMPROMISED! This data does not match the blockchain ledger.\n")
    return False

if __name__ == "__main__":
    # Example 1: Simulating an Auditor checking VALID data
    # (To test this for real, copy a Timestamp from Alethio Lite Explorer)
    print("--- TEST 1: Checking known good data (from verify_blockchain.py) ---")
    
    # Note: verify_blockchain.py didn't include humidity, so we reconstruct its specific dict
    mock_payload = '{"node_id": "TEST_NODE_01", "temperature": 25.5}'
    computed_mock_hash = w3.to_hex(hashlib.sha256(mock_payload.encode('utf-8')).digest())
    
    events = contract.events.TelemetryRecorded.create_filter(from_block=0).get_all_entries()
    found = any(w3.to_hex(e.args.payloadHash) == computed_mock_hash for e in events)
    if found:
         print(f"✅ Found mock hash {computed_mock_hash} in ledger!\n")
    else:
         print("❌ Mock hash not found (did you run verify_blockchain.py?)\n")
    
    # Example 2: Simulating an Auditor checking a specific payload
    print("--- TEST 2: How to check real data ---")
    print("To check your real Raspberry Pi data:")
    print("1. Look at Alethio Lite Explorer and copy the 'Timestamp' column.")
    print("2. Look at Grafana and find the Temperature and Humidity for that exact timestamp.")
    print("3. Call audit_telemetry('amith', temp, hum, ts_ns) in this script to verify it!")

import json
import hashlib
import time
from web3 import Web3

# ── 1. Configuration ───────────────────────────────────────────
BESU_RPC = "http://127.0.0.1:8545"
# Paste the EXACT SAME private key you used in deploy.py
PRIVATE_KEY = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"

print("\n[1/5] Connecting to Hyperledger Besu...")
w3 = Web3(Web3.HTTPProvider(BESU_RPC))

if not w3.is_connected():
    print(f" ❌ ERROR: Cannot connect to Besu node at {BESU_RPC}.")
    print("    Ensure your 4-node Docker infrastructure is running.")
    exit(1)
print(f" ✅ Connected! Chain ID: {w3.eth.chain_id}")

# ── 2. Load Contract Files ─────────────────────────────────────
print("[2/5] Loading Contract Address and ABI...")
try:
    with open("contract_address.txt", "r") as f:
        contract_address = f.read().strip()
    with open("contract_abi.json", "r") as f:
        contract_abi = json.load(f)
    print(f" ✅ Loaded Contract at: {contract_address}")
except FileNotFoundError:
    print(" ❌ ERROR: Missing contract_address.txt or contract_abi.json.")
    print("    Did you run deploy.py first?")
    exit(1)

# ── 3. Bind the Smart Contract ─────────────────────────────────
print("[3/5] Binding Smart Contract...")
contract = w3.eth.contract(address=contract_address, abi=contract_abi)
account = w3.eth.account.from_key(PRIVATE_KEY)

try:
    initial_count = contract.functions.getRecordCount().call()
    print(f" ✅ Contract bound successfully! Current records in ledger: {initial_count}")
except Exception as e:
    print(f" ❌ ERROR: Failed to call getRecordCount(). Is the contract deployed correctly?\n{e}")
    exit(1)

# ── 4. Generate Mock Telemetry Hash ────────────────────────────
print("[4/5] Simulating Decrypted Telemetry Hash...")
mock_payload = '{"node_id": "TEST_NODE_01", "temperature": 25.5}'
payload_hash_hex = hashlib.sha256(mock_payload.encode('utf-8')).hexdigest()
payload_hash_bytes = Web3.to_bytes(hexstr=payload_hash_hex)
current_ts = time.time_ns()

print(f" ℹ️  Generated Hash: 0x{payload_hash_hex}")

# ── 5. Submit Transaction to IBFT 2.0 Ledger ───────────────────
print("[5/5] Submitting Hash to Blockchain...")
try:
    nonce = w3.eth.get_transaction_count(account.address)
    
    # Build the transaction
    txn = contract.functions.recordTelemetry(
        "TEST_NODE_01", 
        current_ts, 
        payload_hash_bytes
    ).build_transaction({
        "chainId": w3.eth.chain_id,
        "gasPrice": w3.eth.gas_price, 
        "gas": 3000000,
        "from": account.address,
        "nonce": nonce,
    })

    # Sign and Send
    signed_txn = w3.eth.account.sign_transaction(txn, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    print(f" ⏳ Transaction Broadcasted: {tx_hash.hex()}")
    
    # Wait for the block to be mined
    print(" ⏳ Waiting for IBFT 2.0 Consensus (should take ~2 seconds)...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    if receipt.status == 1:
        new_count = contract.functions.getRecordCount().call()
        print("\n" + "="*50)
        print(" 🎉 BLOCKCHAIN INTEGRATION VERIFIED!")
        print(f" 📦 Mined in Block : {receipt.blockNumber}")
        print(f" 📊 Total Records  : {new_count}")
        
        # ── Fetch and Decode the Emitted Event ──
        events = contract.events.TelemetryRecorded().process_receipt(receipt)
        if events:
            print("\n 📝 SMART CONTRACT EVENT EMITTED (Decoded):")
            for idx, event in enumerate(events):
                args = event['args']
                print(f"    Event #{idx + 1}: TelemetryRecorded")
                print(f"      - nodeId      : {args['nodeId']}")
                print(f"      - timestamp   : {args['timestamp']}")
                print(f"      - payloadHash : 0x{args['payloadHash'].hex()}")
        else:
            print("\n ⚠️ No events found in the receipt.")
            
        print("="*50)
        print("Your Python pipeline is ready to be injected into server.py.")
    else:
        print(" ❌ ERROR: Transaction reverted by the EVM.")
        
except Exception as e:
    print(f" ❌ ERROR: Transaction failed.\n{e}")
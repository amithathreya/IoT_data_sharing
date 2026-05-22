import json
import hashlib
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from datetime import datetime

w3 = Web3(Web3.HTTPProvider("http://localhost:8545"))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
assert w3.is_connected(), "Cannot connect to Besu"

with open("/home/amith/pqc_project/blockchain/contract.json") as f:
    info = json.load(f)

contract = w3.eth.contract(address=info["address"], abi=info["abi"])

def print_chain_summary():
    total = contract.functions.getTotalRecords().call()
    block = w3.eth.block_number
    print("\n── Ground Truth Store (Besu Blockchain) ─────────────")
    print(f"   Current block : {block}")
    print(f"   Total records : {total}")
    print(f"   Contract      : {info['address']}")
    print("─────────────────────────────────────────────────────")
    for i in range(min(total, 10)):
        h       = contract.functions.allHashes(i).call()
        node_id, _, timestamp, _ = contract.functions.getRecord(h).call()
        ts      = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
        print(f"   [{i+1:3}] {ts} | node={node_id} | hash={h.hex()[:16]}...")
    if total > 10:
        print(f"   ... and {total - 10} more records")
    print()

if __name__ == "__main__":
    print_chain_summary()

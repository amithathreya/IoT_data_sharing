from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from solcx import compile_source
import json, os, time

# Connect to Besu with POA middleware
w3 = Web3(Web3.HTTPProvider("http://localhost:8545"))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
assert w3.is_connected(), "Cannot connect to Besu"
print(f"[Deploy] Connected. Chain ID: {w3.eth.chain_id}")
print(f"[Deploy] Block number: {w3.eth.block_number}")

# Account
PRIVATE_KEY = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"
account     = Account.from_key(PRIVATE_KEY)
deployer    = account.address
balance     = w3.eth.get_balance(deployer)
print(f"[Deploy] Deployer: {deployer}")
print(f"[Deploy] Balance:  {w3.from_wei(balance, 'ether')} ETH")
assert balance > 0, "No balance"

# Compile
contract_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SensorRegistry.sol")
with open(contract_path) as f:
    source = f.read()

print("[Deploy] Compiling...")
compiled    = compile_source(source, output_values=["abi","bin"], solc_version="0.8.19")
contract_id = "<stdin>:SensorRegistry"
abi         = compiled[contract_id]["abi"]
bytecode    = compiled[contract_id]["bin"]
print("[Deploy] Compilation OK")

# Deploy
print("[Deploy] Deploying...")
Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
nonce    = w3.eth.get_transaction_count(deployer)
tx       = Contract.constructor().build_transaction({
    "from":     deployer,
    "nonce":    nonce,
    "gas":      3000000,
    "gasPrice": 0,
})
signed  = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
contract_address = receipt["contractAddress"]
print(f"[Deploy] Contract deployed at: {contract_address}")
print(f"[Deploy] Gas used: {receipt['gasUsed']}")

# Save
output = {"address": contract_address, "abi": abi}
output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contract.json")
with open(output_path, "w") as f:
    json.dump(output, f, indent=2)
print("[Deploy] Saved contract.json")

# Test
print("\n[Deploy] Testing contract...")
contract  = w3.eth.contract(address=contract_address, abi=abi)
test_hash = w3.keccak(text="test_sensor_reading")
nonce     = w3.eth.get_transaction_count(deployer)
tx        = contract.functions.storeRecord(
    "pi-node-1",
    test_hash,
    int(time.time())
).build_transaction({
    "from":     deployer,
    "nonce":    nonce,
    "gas":      200000,
    "gasPrice": 0,
})
signed  = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
w3.eth.wait_for_transaction_receipt(tx_hash)

exists = contract.functions.verifyRecord(test_hash).call()
total  = contract.functions.getTotalRecords().call()
print(f"[Deploy] Test hash verified: {exists}")
print(f"[Deploy] Total records:      {total}")
print("\n[Deploy] ✅ SUCCESS")

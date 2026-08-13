import json
import os
import solcx
from web3 import Web3

# Ensure solc is installed
solcx.install_solc('0.8.0')
from solcx import compile_source

# 1. Connect to Besu
w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))
if not w3.is_connected():
    print("❌ Cannot connect to Besu")
    exit(1)
print("✅ Connected to Besu")

# The default pre-funded account in Besu --network=dev
PRIVATE_KEY = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"
account = w3.eth.account.from_key(PRIVATE_KEY)
print(f"Using account: {account.address}")

# 2. Compile Contract
with open("TelemetryRegistry.sol", "r") as f:
    contract_source_code = f.read()

compiled_sol = compile_source(
    contract_source_code,
    output_values=['abi', 'bin'],
    solc_version='0.8.0'
)

contract_id, contract_interface = compiled_sol.popitem()
abi = contract_interface['abi']
bytecode = contract_interface['bin']

# 3. Deploy Contract
TelemetryRegistry = w3.eth.contract(abi=abi, bytecode=bytecode)

print("Deploying contract...")
transaction = TelemetryRegistry.constructor().build_transaction({
    'from': account.address,
    'nonce': w3.eth.get_transaction_count(account.address),
    'gas': 3000000,
    'gasPrice': w3.eth.gas_price
})

signed_txn = w3.eth.account.sign_transaction(transaction, private_key=PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

contract_address = tx_receipt.contractAddress
print(f"✅ Contract deployed at: {contract_address}")

# 4. Save Address and ABI
with open("contract_address.txt", "w") as f:
    f.write(contract_address)

with open("contract_abi.json", "w") as f:
    json.dump(abi, f)

# 5. Update .env (Optional but good for server.py)
env_lines = []
if os.path.exists(".env"):
    with open(".env", "r") as f:
        env_lines = f.readlines()

new_env = []
for line in env_lines:
    if not line.startswith("CONTRACT_ADDRESS") and not line.startswith("BESU_PRIVATE_KEY"):
        new_env.append(line)

new_env.append(f"\nCONTRACT_ADDRESS={contract_address}\n")
new_env.append(f"BESU_PRIVATE_KEY={PRIVATE_KEY}\n")

with open(".env", "w") as f:
    f.writelines(new_env)

print("✅ Saved contract_address.txt and contract_abi.json")
print("✅ Updated .env file")

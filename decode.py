import json
from web3 import Web3

# 1. Paste your copied INPUT DATA hex from Alethio Explorer here:
INPUT_DATA = "0x953b5526..." # <-- Replace with your actual copied hex

# 2. Load your contract's ABI
with open("contract_abi.json", "r") as f:
    abi = json.load(f)

# 3. Decode!
w3 = Web3()
contract = w3.eth.contract(abi=abi)
func_obj, func_params = contract.decode_function_input(INPUT_DATA)

print(f"Function Called: {func_obj.fn_name}")
print("Parameters Passed:")
for key, value in func_params.items():
    if isinstance(value, bytes):
        print(f"  {key}: 0x{value.hex()}")
    else:
        print(f"  {key}: {value}")
